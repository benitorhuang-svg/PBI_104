"""Reuse the project's proven Python.Execute client without duplicating HTTP code."""

import ast
import json
import random
import re
import threading
import time

import pandas as pd

from .pagination import PageFetchAborted


def client_code(project):
    source = (project / "powerquery/archive/pre-db-etl/01_functions/fx104GetPage.pq").read_text(encoding="utf-8-sig")
    match = re.search(r'Python.Execute\(\s*"((?:[^"]|"")*)",\s*\[config', source, re.S)
    if not match:
        raise ValueError("Cannot locate the trusted Python.Execute client")
    code = match[1].replace('""', '"')
    ast.parse(code)
    return compile(code, "legacy-fx104GetPage.pq/Python.Execute", "exec")


def fetch_page(code, request, page):
    config = {"baseUrl": request["baseUrl"], "keyword": request.get("keyword"),
              "area": request["area"], "jobsource": request["jobsource"],
              "mode": request["mode"], "order": request["order"],
              "jobcat": request.get("jobcat"), "page": page,
              "pagesize": request["pagesize"]}
    namespace = {"config": pd.DataFrame([config])}
    exec(code, namespace)
    response = json.loads(namespace["df_raw_response"].iloc[0]["rawResponseJson"])
    metadata = namespace["df_metadata"].iloc[0].to_dict()
    metadata = {key: (value.item() if hasattr(value, "item") else value)
                for key, value in metadata.items()}
    return {"response": response, "technical": metadata}


class AccessDeniedError(RuntimeError):
    pass


class RetryExhaustedError(RuntimeError):
    pass


class RequestPacer:
    def __init__(self, interval_seconds=0.0):
        if interval_seconds < 0:
            raise ValueError("Request interval must be >= 0")
        self.minimum_interval = float(interval_seconds)
        self.interval_seconds = float(interval_seconds)
        self._next_request = 0.0
        self._success_count = 0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            scheduled = max(now, self._next_request)
            self._next_request = scheduled + self.interval_seconds
        if scheduled > now:
            time.sleep(scheduled - now)

    def succeeded(self):
        with self._lock:
            self._success_count += 1
            if self._success_count >= 20:
                self.interval_seconds = max(self.minimum_interval,
                                            self.interval_seconds * 0.9)
                self._success_count = 0

    def backoff(self, retry_seconds):
        with self._lock:
            self.interval_seconds = max(self.minimum_interval,
                                        self.interval_seconds * 2,
                                        retry_seconds)
            self._next_request = max(self._next_request,
                                     time.monotonic() + self.interval_seconds)
            self._success_count = 0
            return self.interval_seconds


class CategoryRequestStop:
    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._reason = None

    def stop(self, reason):
        with self._lock:
            if self._reason is None:
                self._reason = reason
            self._event.set()

    def check(self):
        if self._event.is_set():
            with self._lock:
                reason = self._reason
            raise PageFetchAborted("Stopped sibling page requests") from reason


class ExponentialBackoff:
    def __init__(self, max_attempts=5, base_seconds=1.0, max_seconds=30.0):
        self.max_attempts = max_attempts
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    def wait(self, stop):
        waited = False
        while True:
            stop.check()
            with self._lock:
                remaining = self._blocked_until - time.monotonic()
            if remaining <= 0:
                return waited
            waited = True
            time.sleep(remaining + random.uniform(0.0, min(0.5, remaining * 0.2)))

    def defer(self, attempt):
        ceiling = min(self.max_seconds, self.base_seconds * (2 ** attempt))
        delay = min(self.max_seconds, ceiling * random.uniform(0.75, 1.25))
        with self._lock:
            self._blocked_until = max(self._blocked_until,
                                      time.monotonic() + delay)
        return delay


_BLOCKING_HTTP = re.compile(r"\b(401|403|407|418)\s+(?:client|server)\s+error\b")
_RETRYABLE_HTTP = re.compile(r"\b(408|425|429|500|502|503|504)\s+(?:client|server)\s+error\b")
_NETWORK_FAILURES = ("timed out", "timeout", "connection aborted", "connection reset",
                     "remote end closed", "connection error", "newconnectionerror",
                     "proxyerror", "name resolution")


def _failure_kind(error):
    message = str(error).lower()
    if any(marker in message for marker in ("invalid json", "cloudflare", "captcha")):
        return "blocked", "challenge-or-non-json-response"
    match = _BLOCKING_HTTP.search(message)
    if match:
        return "blocked", int(match.group(1))
    match = _RETRYABLE_HTTP.search(message)
    if match:
        return "retry", int(match.group(1))
    if any(marker in message for marker in _NETWORK_FAILURES):
        return "retry", "network"
    return "fatal", None


def fetch_page_with_backoff(operation, page, backoff, stop, on_retry):
    for attempt in range(backoff.max_attempts):
        backoff.wait(stop)
        try:
            return operation()
        except Exception as error:
            kind, reason = _failure_kind(error)
            if kind == "blocked":
                failure = AccessDeniedError(f"104 access denied with HTTP {reason}")
                stop.stop(failure)
                raise failure from error
            if kind == "retry":
                if attempt + 1 >= backoff.max_attempts:
                    failure = RetryExhaustedError(
                        f"Page {page} failed after {backoff.max_attempts} attempts")
                    stop.stop(failure)
                    raise failure from error
                delay = backoff.defer(attempt)
                on_retry(page, attempt + 1, delay, reason)
                continue
            stop.stop(error)
            raise
    raise AssertionError("Retry loop ended unexpectedly")
