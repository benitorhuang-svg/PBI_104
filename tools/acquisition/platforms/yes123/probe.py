"""Diagnostic probe for yes123 job acquisition and normalization.

Tests:
1. HTTP session & header resilience against yes123 server.
2. DOM parsing of job cards and extraction of native IDs via Yes123Client.
3. Total job count extraction from meta/DOM.
4. Pagination contract verification using strrec parameter.
5. Integration with existing salary_parser.py and geocoding.py.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from .client import Yes123Client


def run_probe(
    category_code: Optional[str] = None,
    keyword: Optional[str] = None,
    pages: int = 1,
    fixture_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute diagnostic probe and print contract inspection summary."""
    sys.stdout.reconfigure(encoding="utf-8")
    client = Yes123Client(min_interval_seconds=1.5)

    print("=" * 80)
    print("YES123 ACQUISITION & NORMALIZATION DIAGNOSTIC PROBE")
    print("=" * 80)
    print(f"Target Category: {category_code or 'NONE'}")
    print(f"Target Keyword:  {keyword or 'NONE'}")
    print(f"Pages to probe:  {pages}")
    print("-" * 80)

    batch = client.collect(
        category_code=category_code,
        keyword=keyword,
        max_pages=pages,
    )

    all_jobs = batch["jobs"]
    total_reported = batch["reported_total"]
    raw_pages = batch["pages"]

    for p in raw_pages:
        print(
            f"[Page {p['page']}] strrec={p['strrec']:3d} | "
            f"HTTP {p['status_code']} | "
            f"Bytes: {p['bytes_length']:6d} | "
            f"Jobs: {p['rows_found']} (New: {p['new_rows']})"
        )

    print("-" * 80)
    print(f"Reported Total Jobs:  {total_reported if total_reported is not None else 'UNKNOWN'}")
    print(f"Total Jobs Collected: {len(all_jobs)}")

    missing_job_id = sum(1 for j in all_jobs if not j.get("native_job_id"))
    missing_comp_id = sum(1 for j in all_jobs if not j.get("native_company_id"))
    parsed_salaries = sum(
        1 for j in all_jobs
        if any(o.get("parse_status") != "NEEDS_REVIEW" for o in j.get("salary_observations", []))
    )
    standardized_addrs = sum(1 for j in all_jobs if j.get("standardized_address"))

    print("\n--- DATA CONTRACT & QUALITY METRICS ---")
    print(f"Unique Jobs (by native_job_id):     {len({j['native_job_id'] for j in all_jobs if j.get('native_job_id')})}")
    print(f"Unique Companies (by comp_id):      {len({j['native_company_id'] for j in all_jobs if j.get('native_company_id')})}")
    print(f"Missing Native Job ID:              {missing_job_id}")
    print(f"Missing Native Company ID:          {missing_comp_id}")
    print(f"Salary Parse Success Rate:          {parsed_salaries}/{len(all_jobs)} ({parsed_salaries / max(1, len(all_jobs)):.1%})")
    print(f"Address Standardized Rate:          {standardized_addrs}/{len(all_jobs)} ({standardized_addrs / max(1, len(all_jobs)):.1%})")

    print("\n--- SAMPLE EXTRACTED RECORDS (FIRST 3) ---")
    for idx, j in enumerate(all_jobs[:3]):
        sal_obs = [o for o in j.get("salary_observations", []) if o.get("source_kind") == "DESCRIPTION"]
        sal = sal_obs[0] if sal_obs else {}
        sal_desc = (
            f"status={sal.get('parse_status')}, min={sal.get('amount_min')}, max={sal.get('amount_max')}, "
            f"period={sal.get('pay_period')}, kind={sal.get('range_kind')}"
            if sal else "None"
        )
        print(f"[{idx+1}] {j.get('job_title')} @ {j.get('company_name')}")
        print(f"    SK:         {j.get('source_job_key')}")
        print(f"    Company SK: {j.get('source_company_key')}")
        print(f"    Raw Salary: {j.get('raw_salary')} -> {sal_desc}")
        print(f"    Location:   {j.get('raw_area')} -> Standardized: {j.get('standardized_address')}")
        print(f"    Link:       {j.get('job_url')}")

    probe_result = {
        "status": "PASS" if all_jobs and missing_job_id == 0 else "FAIL",
        "target_category": category_code,
        "target_keyword": keyword,
        "reported_total": total_reported,
        "collected_total": len(all_jobs),
        "metrics": {
            "missing_job_id": missing_job_id,
            "missing_comp_id": missing_comp_id,
            "parsed_salaries": parsed_salaries,
            "standardized_addrs": standardized_addrs,
        },
        "pages": raw_pages,
        "sample_jobs": all_jobs[:10],
    }

    if fixture_path:
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        def decimal_default(obj: Any) -> Any:
            if isinstance(obj, Decimal):
                return str(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        fixture_path.write_text(
            json.dumps(probe_result, ensure_ascii=False, indent=2, default=decimal_default),
            encoding="utf-8",
        )
        print(f"\n[Artifact Saved] Diagnostic result saved to {fixture_path}")

    print("=" * 80)
    return probe_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic probe for yes123 job acquisition")
    parser.add_argument(
        "--category",
        type=str,
        default="2_1006_0002_0003",
        help="yes123 work_mode category code",
    )
    parser.add_argument("--keyword", type=str, default=None, help="Search keyword")
    parser.add_argument("--pages", type=int, default=2, help="Pages to probe")
    parser.add_argument(
        "--save-fixture",
        type=str,
        default="tools/tests/fixtures/yes123-sample-probe.json",
        help="Path to save JSON fixture",
    )
    args = parser.parse_args()

    fixture = PROJECT_ROOT / args.save_fixture if args.save_fixture else None
    run_probe(
        category_code=args.category,
        keyword=args.keyword,
        pages=args.pages,
        fixture_path=fixture,
    )


if __name__ == "__main__":
    main()
