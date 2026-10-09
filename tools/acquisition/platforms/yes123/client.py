"""Acquisition client for yes123 job bank with adaptive annealing rate control."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

import requests
from bs4 import BeautifulSoup

from .annealer import AnnealingPacer
from .parser import (
    compute_series_key,
    extract_reported_total,
    parse_job_cards,
    is_taiwan_location,
    parse_job_detail_dom,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.yes123.com.tw/admin/job_refer_list.asp",
}

BASE_SEARCH_URL = "https://www.yes123.com.tw/admin/job_refer_list.asp"


class Yes123Client:
    """Client for fetching and packaging yes123 batches with adaptive pacing."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        min_interval_seconds: float = 1.5,
        timeout_seconds: float = 15.0,
        pacer: Optional[AnnealingPacer] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout_seconds
        self.pacer = pacer or AnnealingPacer(
            min_interval=min_interval_seconds,
            initial_interval=max(2.0, min_interval_seconds),
        )

    def fetch_page(
        self,
        category_code: Optional[str] = None,
        keyword: Optional[str] = None,
        strrec: int = 0,
    ) -> Tuple[int, bytes, List[Dict[str, Any]], Optional[int]]:
        """Fetch single search page with adaptive retry and return parsed records."""
        params: Dict[str, Any] = {"strrec": strrec}
        if category_code:
            params["find_work_mode1"] = category_code
        if keyword:
            params["find_key1"] = keyword

        attempt = 0
        while True:
            attempt += 1
            self.pacer.acquire()
            t0 = time.monotonic()
            try:
                resp = self.session.get(
                    BASE_SEARCH_URL,
                    params=params,
                    headers=DEFAULT_HEADERS,
                    timeout=self.timeout,
                )
                latency = time.monotonic() - t0
                status_code = resp.status_code

                if status_code == 200:
                    content_bytes = resp.content
                    # Check for WAF challenge or captcha interstitial
                    text_head = content_bytes[:4000].decode("utf-8", errors="replace")
                    if any(bad in text_head for bad in ["訪問異常", "請完成驗證", "Attention Required!"]):
                        if attempt < self.pacer.max_retries:
                            self.pacer.on_throttle(429, reason="captcha_detected")
                            continue
                        raise PermissionError("WAF challenge or verification interstitial encountered")

                    self.pacer.on_success(latency)
                    soup = BeautifulSoup(content_bytes, "html.parser", from_encoding="utf-8")
                    reported_total = extract_reported_total(soup)
                    jobs = parse_job_cards(soup)
                    return status_code, content_bytes, jobs, reported_total

                if status_code in (429, 503, 502, 504):
                    retry_header = resp.headers.get("Retry-After")
                    retry_sec = float(retry_header) if retry_header and retry_header.isdigit() else None
                    if attempt < self.pacer.max_retries:
                        self.pacer.on_throttle(status_code, retry_after=retry_sec)
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()

            except (requests.RequestException, TimeoutError) as net_err:
                if attempt < self.pacer.max_retries:
                    self.pacer.on_throttle(503, reason=str(net_err))
                    continue
                raise

    def collect(
        self,
        category_code: Optional[str] = None,
        keyword: Optional[str] = None,
        max_pages: Optional[int] = None,
        snapshot_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Fetch all pages for a category query and assemble batch payload."""
        now = snapshot_time or datetime.now(timezone.utc)
        request = {
            "platform": "yes123",
            "category_code": category_code,
            "keyword": keyword,
            "baseUrl": BASE_SEARCH_URL,
        }
        series_key = compute_series_key(request)
        batch_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}"

        seen_job_ids = set()
        all_jobs: List[Dict[str, Any]] = []
        page_records: List[Dict[str, Any]] = []
        raw_rows: List[Tuple[int, int, Dict[str, Any]]] = []

        page_num = 1
        reported_total: Optional[int] = None

        while True:
            if max_pages is not None and page_num > max_pages:
                break

            strrec = (page_num - 1) * 30
            if reported_total is not None and strrec >= reported_total:
                break

            status_code, content, jobs_in_page, page_total = self.fetch_page(
                category_code=category_code,
                keyword=keyword,
                strrec=strrec,
            )

            if page_num == 1 and page_total is not None:
                reported_total = page_total

            content_sha256 = hashlib.sha256(content).hexdigest()
            new_jobs = [j for j in jobs_in_page if j["native_job_id"] not in seen_job_ids]

            # Wrap-around termination check
            if page_num > 1 and not new_jobs:
                break

            for row_idx, job in enumerate(new_jobs):
                seen_job_ids.add(job["native_job_id"])
                all_jobs.append(job)
                raw_rows.append((page_num, row_idx, job))

            page_records.append({
                "page": page_num,
                "strrec": strrec,
                "status_code": status_code,
                "sha256": content_sha256,
                "bytes_length": len(content),
                "rows_found": len(jobs_in_page),
                "new_rows": len(new_jobs),
            })

            page_num += 1

        manifest = {
            "schemaVersion": 1,
            "sourcePlatform": "yes123",
            "codeKind": "YES123_WORK_MODE" if category_code else "KEYWORD",
            "nativeSearchCode": category_code or keyword,
            "seriesKey": series_key,
            "batchId": batch_id,
            "snapshotDate": now.date().isoformat(),
            "snapshotDateTime": now.isoformat(),
            "request": request,
            "reportedTotal": reported_total,
            "pages": page_records,
            "rows": len(all_jobs),
            "paginationStatus": "PASS",
        }
        manifest_sha256 = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode("utf-8")
        ).hexdigest()
        manifest["manifestSha256"] = manifest_sha256

        return {
            "manifest": manifest,
            "manifest_sha256": manifest_sha256,
            "series_key": series_key,
            "batch_id": batch_id,
            "snapshot_date": now.date().isoformat(),
            "snapshot_datetime": now,
            "capture_status": "COMPLETE",
            "reported_total": reported_total,
            "jobs": all_jobs,
            "raw_rows": raw_rows,
            "pages": page_records,
            "pacer_metrics": self.pacer.metrics(),
        }
