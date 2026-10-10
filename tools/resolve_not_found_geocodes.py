"""Targeted recovery worker for addresses previously marked NOT_FOUND."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import psycopg
import requests

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from acquisition.platforms.jobwant_104.persistence.loader import read_db_config
from acquisition.platforms.yes123.enricher import (
    clean_address_noise,
    extract_coords_from_gmaps_embed,
    write_sqlite_alias,
    LOCAL_GEOCODER_URL,
)


def run_recovery(
    workers: int = 5,
    dbname: str = "jobwant_yes123",
    env_file: Path = Path(".env"),
) -> Dict[str, Any]:
    """Re-query and recover coordinates for addresses currently marked NOT_FOUND."""
    db_config = read_db_config(env_file)
    db_config["dbname"] = dbname

    with psycopg.connect(**db_config) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT area_key, input_address, google_maps_search_url
                FROM silver.address_geocodes
                WHERE match_level = 'NOT_FOUND'
                ORDER BY area_key;
            """)
            pending = [
                {"area_key": r[0], "input_address": r[1], "google_maps_search_url": r[2]}
                for r in cur.fetchall()
            ]

    total = len(pending)
    print(f"Total NOT_FOUND addresses to re-evaluate: {total} (Workers: {workers})")
    if total == 0:
        print("No NOT_FOUND addresses. Nothing to recover.")
        return {"recovered": 0, "total": 0}

    work_q: queue.Queue = queue.Queue()
    for item in pending:
        work_q.put(item)

    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    processed = 0
    recovered = 0
    genuine_not_found = 0
    t0 = time.monotonic()

    def worker_loop(wid: int) -> None:
        nonlocal processed, recovered, genuine_not_found
        session = requests.Session()
        with psycopg.connect(**db_config) as conn:
            while True:
                try:
                    item = work_q.get_nowait()
                except queue.Empty:
                    break

                    akey = item["area_key"]
                    raw_addr = item["input_address"] or akey.replace("||", "")
                    clean_addr = clean_address_noise(raw_addr)

                try:
                    akey = item["area_key"]
                    raw_addr = item["input_address"] or akey.replace("||", "")
                    clean_addr = clean_address_noise(raw_addr)

                    target_url = item["google_maps_search_url"] or f"https://maps.google.com.tw/maps?q={quote(clean_addr)}&z=16&output=embed"
                    glat, glng = extract_coords_from_gmaps_embed(target_url, session)

                    if glat is None or glng is None:
                        clean_url = f"https://maps.google.com.tw/maps?q={quote(clean_addr)}&z=16&output=embed"
                        glat, glng = extract_coords_from_gmaps_embed(clean_url, session)

                    with stats_lock:
                        processed += 1
                        curr_cnt = processed
                        if glat is not None and glng is not None:
                            recovered += 1
                        else:
                            genuine_not_found += 1

                    if glat is not None and glng is not None:
                        dlat, dlng = Decimal(str(round(glat, 7))), Decimal(str(round(glng, 7)))
                        write_sqlite_alias(clean_addr, glat, glng)
                        with conn.transaction():
                            with conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE silver.area_dimension
                                    SET latitude = %s, longitude = %s
                                    WHERE area_key = %s;
                                """, (dlat, dlng, akey))
                                cur.execute("""
                                    UPDATE silver.address_geocodes
                                    SET latitude = %s, longitude = %s,
                                        match_level = 'POI_ALIAS',
                                        strategy = 'RECOVERY_PASS_GMAPS',
                                        geocoded_at = CURRENT_TIMESTAMP
                                    WHERE area_key = %s;
                                """, (dlat, dlng, akey))

                    if curr_cnt % 20 == 0 or curr_cnt == total:
                        pct = (curr_cnt / total) * 100
                        with print_lock:
                            print(f"[{curr_cnt}/{total}] ({pct:5.1f}%) Recovered: {recovered} | Still NotFound: {genuine_not_found}")
                except Exception as err:
                    with print_lock:
                        print(f"[W{wid}] Error on {item['area_key']}: {err}")
                finally:
                    work_q.task_done()

    threads = []
    num_threads = min(workers, total)
    for w in range(1, num_threads + 1):
        t = threading.Thread(target=worker_loop, args=(w,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    elapsed = round(time.monotonic() - t0, 2)
    print("=" * 80)
    print(f"Recovery finished in {elapsed}s: Recovered {recovered}/{total} addresses ({recovered/total*100:.1f}%)")
    print(f"Genuine non-doorplate locations: {genuine_not_found}")
    print("=" * 80)
    return {"total": total, "recovered": recovered, "genuine_not_found": genuine_not_found}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--dbname", type=str, default="jobwant_yes123")
    args = parser.parse_args()
    raise SystemExit(run_recovery(workers=args.workers, dbname=args.dbname))
