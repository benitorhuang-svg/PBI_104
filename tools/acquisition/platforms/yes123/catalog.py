"""Category catalogue fetcher and database crosswalk synchronization for yes123."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import requests

WORK_MODE_JSON_URL = "https://www.yes123.com.tw/json_file/work_mode.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/javascript,*/*;q=0.01",
}


def fetch_work_mode_catalog(
    url: str = WORK_MODE_JSON_URL,
    timeout: float = 15.0,
) -> List[Dict[str, str]]:
    """Fetch official yes123 work_mode.json and parse into flattened category list."""
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.encoding = "utf-8-sig"
    payload = resp.json()
    root_list = payload.get("listObj", [])

    categories: List[Dict[str, str]] = []
    for group in root_list:
        group_name = str(group.get("level_1_name") or "").strip()
        for child in group.get("list_2", []):
            code = str(child.get("code") or "").strip()
            name = str(child.get("level_2_name") or "").strip()
            if code and name:
                categories.append({
                    "code": code,
                    "name": name,
                    "group_name": group_name,
                })
    return categories


def seed_categories_to_crosswalk(conn: Any, categories: List[Dict[str, str]]) -> int:
    """Register all yes123 categories into silver.category_crosswalk idempotently."""
    rows = [
        ("yes123", c["code"], c["name"], "UNMAPPED", 0.0, f"Auto-seeded from yes123 work_mode.json ({c['group_name']})")
        for c in categories
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO silver.category_crosswalk (
                source_platform, native_category_code, native_category_name,
                canonical_job_cat_code, mapping_status, match_confidence, notes
            ) VALUES (%s, %s, %s, NULL, %s, %s, %s)
            ON CONFLICT (source_platform, native_category_code) DO UPDATE SET
                native_category_name = EXCLUDED.native_category_name,
                updated_at = CURRENT_TIMESTAMP
            WHERE silver.category_crosswalk.mapping_status != 'CONFIRMED'""",
            rows,
        )
    return len(rows)


def get_completed_category_codes(conn: Any) -> Set[str]:
    """Return set of yes123 category codes already captured today."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT native_search_code
            FROM bronze.capture_batches
            WHERE source_platform = 'yes123'
              AND snapshot_date = CURRENT_DATE
              AND capture_status = 'COMPLETE'
              AND native_search_code IS NOT NULL"""
        )
        return {str(row[0]) for row in cur.fetchall()}
