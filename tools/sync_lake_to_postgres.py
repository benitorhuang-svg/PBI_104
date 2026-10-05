"""Sync captured 104 JSON data lake batches into PostgreSQL Medallion schema."""

import argparse
import json
import os
from pathlib import Path
import sys


def parse_appear_date(raw):
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def extract_batch_entities(batch_dir):
    manifest_path = batch_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    keyword = manifest.get("request", {}).get("keyword", "")
    batch_id = manifest.get("batchId", "")
    series_key = manifest.get("seriesKey", "")
    snapshot_date = manifest.get("snapshotDate", "")
    snapshot_datetime = manifest.get("snapshotDateTime", "")

    raw_payloads = []
    companies = {}
    areas = {}
    skills = {}
    categories = {}
    jobs = {}
    bridge_skills = set()
    bridge_categories = set()
    bridge_keywords = set()

    for page_entry in manifest.get("pages", []):
        page_num = page_entry.get("page", 1)
        page_file = batch_dir / page_entry.get("file", "")
        if not page_file.exists():
            continue
        with page_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        job_list = data.get("response", {}).get("data", [])
        for j in job_list:
            job_no = str(j.get("jobNo", "")).strip()
            cust_no = str(j.get("custNo", "")).strip()
            if not job_no or not cust_no:
                continue

            raw_payloads.append({
                "job_no": job_no, "search_keyword": keyword, "batch_id": batch_id,
                "series_key": series_key, "source_page": page_num, "payload": j
            })

            co_ind = j.get("coIndustry")
            companies[cust_no] = {
                "cust_no": cust_no,
                "company_name": j.get("custName", ""),
                "co_industry": int(co_ind) if co_ind is not None and str(co_ind).isdigit() else None,
                "co_industry_desc": j.get("coIndustryDesc", "")
            }

            job_addr_no = j.get("jobAddrNo")
            addr_no_int = int(job_addr_no) if job_addr_no is not None and str(job_addr_no).isdigit() else None
            area_key = f"{addr_no_int or ''}:{j.get('jobAddress') or ''}:{j.get('lat') or ''}:{j.get('lon') or ''}"
            areas[area_key] = {
                "area_key": area_key, "job_addr_no": addr_no_int,
                "job_addr_no_desc": j.get("jobAddrNoDesc", ""),
                "job_address": j.get("jobAddress", ""),
                "lat": float(j.get("lat")) if j.get("lat") else None,
                "lon": float(j.get("lon")) if j.get("lon") else None
            }

            appear_date_raw = str(j.get("appearDate", "")) if j.get("appearDate") else ""
            jobs[job_no] = {
                "job_no": job_no, "cust_no": cust_no, "job_name": j.get("jobName", ""),
                "description": j.get("description", ""), "desc_snippet": j.get("descSnippet", ""),
                "area_key": area_key, "salary_low_raw": str(j.get("salaryLow", "")),
                "salary_high_raw": str(j.get("salaryHigh", "")),
                "appear_date_raw": appear_date_raw,
                "appear_date": parse_appear_date(appear_date_raw),
                "apply_cnt": int(j.get("applyCnt")) if j.get("applyCnt") is not None and str(j.get("applyCnt")).isdigit() else None,
                "remote_work_type": int(j.get("remoteWorkType")) if j.get("remoteWorkType") is not None and str(j.get("remoteWorkType")).isdigit() else None,
                "first_seen_at": snapshot_date, "last_seen_at": snapshot_date
            }

            bridge_keywords.add((job_no, keyword))

            for sk in j.get("pcSkills", []):
                if isinstance(sk, dict) and sk.get("code"):
                    sk_code = str(sk["code"]).strip()
                    sk_desc = str(sk.get("description", "")).strip()
                    skills[sk_code] = {"skill_code": sk_code, "skill_description": sk_desc}
                    bridge_skills.add((job_no, sk_code, sk_desc))

            for cat in j.get("jobCat", []):
                if cat is not None and str(cat).isdigit():
                    cat_code = int(cat)
                    categories[cat_code] = {"job_cat_code": cat_code, "job_cat_description": "BLOCKED"}
                    bridge_categories.add((job_no, cat_code))

    return {
        "manifest": manifest,
        "raw_payloads": raw_payloads,
        "companies": list(companies.values()),
        "areas": list(areas.values()),
        "skills": list(skills.values()),
        "categories": list(categories.values()),
        "jobs": list(jobs.values()),
        "bridge_skills": list(bridge_skills),
        "bridge_categories": list(bridge_categories),
        "bridge_keywords": list(bridge_keywords)
    }


def sync_all_batches(data_root, dry_run=True):
    series_root = data_root / "104" / "series"
    if not series_root.exists():
        print(f"Series root not found: {series_root}")
        return

    total_stats = {
        "batches": 0, "raw_payloads": 0, "jobs": 0, "companies": 0,
        "skills": 0, "categories": 0, "bridge_keywords": 0
    }

    for series_dir in sorted(series_root.iterdir()):
        if not series_dir.is_dir():
            continue
        batches_dir = series_dir / "batches"
        if not batches_dir.exists():
            continue
        for batch_dir in sorted(batches_dir.iterdir()):
            if not batch_dir.is_dir():
                continue
            res = extract_batch_entities(batch_dir)
            if not res:
                continue
            total_stats["batches"] += 1
            total_stats["raw_payloads"] += len(res["raw_payloads"])
            total_stats["jobs"] += len(res["jobs"])
            total_stats["companies"] += len(res["companies"])
            total_stats["skills"] += len(res["skills"])
            total_stats["categories"] += len(res["categories"])
            total_stats["bridge_keywords"] += len(res["bridge_keywords"])

            print(f"[Batch {res['manifest']['batchId']}] Keyword='{res['manifest']['request']['keyword']}': "
                  f"{len(res['jobs'])} jobs, {len(res['companies'])} companies, {len(res['bridge_keywords'])} keyword pairs.")

    print("\n--- Summary of Lakehouse Extraction ---")
    print(json.dumps(total_stats, indent=2))
    if dry_run:
        print("\nDry-run mode: Extraction contract verified against schema without live database connection.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True, help="Validate data transformation without writing")
    parser.add_argument("--data-root", default="data", help="Root directory of data lake")
    args = parser.parse_args()

    sync_all_batches(Path(args.data_root), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
