"""Database-coordinated request pacing and exponential retry across workers."""

import random
import threading
import time

import psycopg

from ..client.embedded_client import AccessDeniedError


class DistributedRequestState:
    CHANNEL = "104_jobs"
    SUCCESS_WINDOW = 20
    SUCCESS_REDUCTION = 0.9
    BACKOFF_MULTIPLIER = 1.5

    def __init__(self, config, minimum_interval=0.8, maximum_interval=8.0):
        self.conn = psycopg.connect(**config)
        self.lock = threading.Lock()
        self.base_seconds = 1.0
        self.max_backoff_seconds = 300.0
        self.configure(minimum_interval, maximum_interval)

    def configure(self, minimum_interval, maximum_interval=8.0):
        maximum_interval = max(float(maximum_interval), float(minimum_interval))
        with self.conn.transaction():
            self.conn.execute("""UPDATE bronze.capture_request_state
                SET minimum_interval_seconds = %s,
                    maximum_interval_seconds = %s,
                    interval_seconds = LEAST(%s,
                        GREATEST(interval_seconds, %s)),
                    updated_at = clock_timestamp()
                WHERE channel = %s""",
                (minimum_interval, maximum_interval, maximum_interval,
                 minimum_interval, self.CHANNEL))

    def acquire(self, stop):
        while True:
            stop.check()
            with self.lock, self.conn.transaction():
                row = self.conn.execute("""SELECT minimum_interval_seconds,
                    interval_seconds, next_request_at, blocked_until, blocked_reason
                    FROM bronze.capture_request_state WHERE channel = %s FOR UPDATE""",
                    (self.CHANNEL,)).fetchone()
                if not row:
                    raise RuntimeError("Distributed request state is not initialized")
                _, interval, next_at, blocked_until, blocked_reason = row
                if blocked_reason:
                    raise AccessDeniedError(f"Distributed API gate is blocked: {blocked_reason}")
                now = self.conn.execute("SELECT clock_timestamp()").fetchone()[0]
                ready_at = max(next_at, blocked_until)
                remaining = (ready_at - now).total_seconds()
                if remaining <= 0:
                    self.conn.execute("""UPDATE bronze.capture_request_state
                        SET next_request_at = %s + (%s * interval '1 second'),
                            updated_at = %s WHERE channel = %s""",
                        (now, interval, now, self.CHANNEL))
                    return
            stop.wait(min(remaining, 1.0))

    def succeeded(self):
        with self.lock, self.conn.transaction():
            self.conn.execute("""UPDATE bronze.capture_request_state
                SET interval_seconds = CASE WHEN success_count + 1 >= %s
                    THEN GREATEST(minimum_interval_seconds,
                                 interval_seconds * %s)
                    ELSE interval_seconds END,
                    success_count = CASE WHEN success_count + 1 >= %s
                        THEN 0 ELSE success_count + 1 END,
                    updated_at = clock_timestamp()
                WHERE channel = %s""",
                (self.SUCCESS_WINDOW, self.SUCCESS_REDUCTION,
                 self.SUCCESS_WINDOW, self.CHANNEL))

    def on_429(self, retry_seconds):
        with self.lock, self.conn.transaction():
            row = self.conn.execute("""SELECT interval_seconds,
                maximum_interval_seconds FROM bronze.capture_request_state
                WHERE channel = %s FOR UPDATE""", (self.CHANNEL,)).fetchone()
            interval = min(row[1], max(row[0] * self.BACKOFF_MULTIPLIER,
                                      retry_seconds))
            self.conn.execute("""UPDATE bronze.capture_request_state
                SET interval_seconds = %s, success_count = 0,
                    next_request_at = GREATEST(next_request_at,
                        clock_timestamp() + (%s * interval '1 second')),
                    updated_at = clock_timestamp() WHERE channel = %s""",
                (interval, interval, self.CHANNEL))
            return interval

    def defer(self, attempt):
        exponent = min(attempt, 16)
        ceiling = min(self.max_backoff_seconds, self.base_seconds * (2 ** exponent))
        delay = min(self.max_backoff_seconds, ceiling * random.uniform(0.75, 1.0))
        with self.lock, self.conn.transaction():
            self.conn.execute("""UPDATE bronze.capture_request_state
                SET blocked_until = GREATEST(blocked_until,
                    clock_timestamp() + (%s * interval '1 second')),
                    updated_at = clock_timestamp() WHERE channel = %s""",
                (delay, self.CHANNEL))
        return delay

    def wait_retry(self, stop):
        waited = False
        while True:
            stop.check()
            with self.lock, self.conn.transaction():
                row = self.conn.execute("""SELECT blocked_until, blocked_reason
                    FROM bronze.capture_request_state WHERE channel = %s""",
                    (self.CHANNEL,)).fetchone()
                if not row:
                    raise RuntimeError("Distributed retry state is not initialized")
                if row[1]:
                    raise AccessDeniedError(f"Distributed API gate is blocked: {row[1]}")
                remaining = (row[0] - self.conn.execute(
                    "SELECT clock_timestamp()").fetchone()[0]).total_seconds()
            if remaining <= 0:
                return waited
            waited = True
            stop.wait(min(remaining + random.uniform(0, min(0.5, remaining * 0.2)), 1.0))

    def block(self, reason):
        with self.lock, self.conn.transaction():
            self.conn.execute("""UPDATE bronze.capture_request_state
                SET blocked_reason = COALESCE(blocked_reason, %s),
                    updated_at = clock_timestamp() WHERE channel = %s""",
                (str(reason)[:1000], self.CHANNEL))

    def interval_seconds(self):
        with self.lock, self.conn.transaction():
            return self.conn.execute("""SELECT interval_seconds
                FROM bronze.capture_request_state WHERE channel = %s""",
                (self.CHANNEL,)).fetchone()[0]

    def close(self):
        self.conn.close()


class DistributedRequestPacer:
    def __init__(self, state):
        self.state = state

    def wait(self):
        self.state.acquire(_NeverStop())

    def succeeded(self):
        self.state.succeeded()

    def backoff(self, retry_seconds):
        return self.state.on_429(retry_seconds)

    def block(self, reason):
        self.state.block(reason)


class DistributedExponentialBackoff:
    def __init__(self, state):
        self.state = state

    def wait(self, stop):
        return self.state.wait_retry(stop)

    def defer(self, attempt):
        return self.state.defer(attempt)


class _NeverStop:
    def check(self):
        return None

    def wait(self, seconds):
        time.sleep(seconds)
