"""PostgreSQL loader and normalizer for yes123 batches."""

from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
import json, re
from pathlib import Path
from typing import Any, Dict, List, Optional
from ...shared.geocoding import standardize_taiwan_address
from ...shared.postgres_schema import apply_schema

def clean_text(val: Any) -> Optional[str]:
    return "".join(c for c in str(val) if ord(c) >= 32).strip() or None if val is not None else None

def normalize_company_name(raw: str) -> str:
    cleaned = re.sub(r"(?:股份有限公司|有限公司|企業社|商行|工作室|分公司|辦事處|集團)", "", raw)
    return re.sub(r"[\(\)（）\s_\-－]", "", cleaned).strip() or raw.strip()

def parse_date_str(raw: Optional[str], year: int) -> Optional[date]:
    if not raw: return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})", raw)
    if not m: return None
    try: return date(year, int(m.group(1)), int(m.group(2)))
    except ValueError: return None

def _many(conn: Any, stmt: str, rows: List[Any]) -> None:
    if rows:
        with conn.cursor() as cur: cur.executemany(stmt, rows)

def save_yes123_batch(conn: Any, batch: Dict[str, Any], Jsonb: Any) -> Dict[str, Any]:
    def _jb(val: Any) -> Any:
        try:
            return Jsonb(val, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))
        except TypeError:
            return Jsonb(val)

    man = batch["manifest"]
    bid, skey = man["batchId"], man["seriesKey"]
    sdate = date.fromisoformat(man["snapshotDate"])
    stime = datetime.fromisoformat(man["snapshotDateTime"])
    req = man["request"]
    ccode, kw = req.get("category_code"), req.get("keyword")

    conn.execute(
        """INSERT INTO bronze.capture_batches (batch_id, series_key, snapshot_date, snapshot_datetime,
        source_jobcat, request, manifest_sha256, manifest, row_count, capture_status,
        source_platform, code_kind, native_search_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (batch_id) DO NOTHING""",
        (bid, skey, sdate, stime, ccode, _jb(req), batch["manifest_sha256"],
         _jb(man), man["rows"], "COMPLETE", "yes123", man.get("codeKind", "YES123_WORK_MODE"), ccode or kw)
    )

    raws = [(bid, p, idx, j["native_job_id"], _jb(j), json.dumps(j, ensure_ascii=False, default=str),
             _jb([]), "yes123", j["native_job_id"]) for p, idx, j in batch["raw_rows"]]
    _many(conn, """INSERT INTO bronze.raw_job_rows (batch_id, source_page, row_index, job_no, payload,
        payload_source_json, payload_quality_flags, source_platform, native_job_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (batch_id, source_page, row_index) DO NOTHING""", raws)

    jobs = batch["jobs"]
    if not jobs: return {"batch_id": bid, "status": "loaded-empty", "rows": 0, "jobs": 0}

    comps: Dict[str, Dict[str, Any]] = {}
    for j in jobs:
        cid = j["native_company_id"]
        if cid and cid not in comps:
            comps[cid] = {"cust_no": f"yes123:{cid}", "name": j["company_name"], "norm": normalize_company_name(j["company_name"])}

    _many(conn, """INSERT INTO silver.company_dimension (cust_no, company_name, co_industry, co_industry_desc)
        VALUES (%s, %s, %s, %s) ON CONFLICT (cust_no) DO UPDATE SET
        company_name = COALESCE(EXCLUDED.company_name, silver.company_dimension.company_name), updated_at = CURRENT_TIMESTAMP""",
        [(c["cust_no"], c["name"], None, None) for c in comps.values()])

    _many(conn, """INSERT INTO silver.company_master (company_master_sk, display_name, normalized_name, business_tax_id)
        VALUES (%s, %s, %s, %s) ON CONFLICT (company_master_sk) DO NOTHING""",
        [(f"yes123:{cid}", c["name"], c["norm"], None) for cid, c in comps.items()])

    _many(conn, """INSERT INTO silver.company_source_mapping (source_platform, native_company_id, raw_company_name, company_master_sk, match_method)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (source_platform, native_company_id) DO NOTHING""",
        [("yes123", cid, c["name"], f"yes123:{cid}", "PLATFORM_DEFAULT") for cid, c in comps.items()])

    areas = {addr: f"||{addr}||" for addr in {j.get("standardized_address") or standardize_taiwan_address(j.get("raw_area") or "") for j in jobs} if addr}
    _many(conn, """INSERT INTO silver.area_dimension (area_key, job_addr_no, job_addr_no_desc, job_address, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (area_key) DO NOTHING""",
        [(k, None, None, addr, None, None) for addr, k in areas.items()])

    currents, snaps = [], []
    for j in jobs:
        nid, cid = j["native_job_id"], j["native_company_id"]
        sjkey = f"yes123:{nid}"
        cno = f"yes123:{cid}" if cid else "yes123:unknown"
        norm_addr = j.get("standardized_address") or ""
        akey = areas.get(norm_addr)
        dobs = [o for o in j.get("salary_observations", []) if o.get("source_kind") == "DESCRIPTION"]
        pobs = dobs[0] if dobs else {}
        slow = Decimal(str(pobs["amount_min"])) if pobs.get("amount_min") is not None else None
        shigh = Decimal(str(pobs["amount_max"])) if pobs.get("amount_max") is not None else None
        appd = parse_date_str(j.get("appear_date_raw"), sdate.year) or sdate

        currents.append((sjkey, cno, j["job_title"], j["raw_salary"], j["job_title"], akey, slow, shigh,
            str(slow) if slow else None, str(shigh) if shigh else None, appd, j.get("appear_date_raw"),
            None, None, j["job_url"], sdate, sdate, stime, skey, kw, ccode, norm_addr, _jb([]), "yes123", nid, sjkey))

        snaps.append((skey, sdate, bid, sjkey, stime, cno, akey, slow, shigh,
            str(slow) if slow else None, str(shigh) if shigh else None, appd, j.get("appear_date_raw"),
            None, None, kw, ccode, norm_addr, 1, 30, _jb([]), "yes123", nid, sjkey))

    _many(conn, """INSERT INTO silver.job_current (job_no, cust_no, job_name, description, desc_snippet, area_key,
        salary_low, salary_high, salary_low_raw, salary_high_raw, appear_date, appear_date_raw, apply_cnt, remote_work_type,
        job_link, first_seen_date, last_seen_date, last_observed_at, source_series_key, source_keyword, source_jobcat,
        source_area, quality_issues, source_platform, native_job_id, source_job_key)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_no) DO UPDATE SET cust_no = EXCLUDED.cust_no, job_name = EXCLUDED.job_name,
        description = EXCLUDED.description, area_key = EXCLUDED.area_key, salary_low = EXCLUDED.salary_low,
        salary_high = EXCLUDED.salary_high, last_seen_date = GREATEST(silver.job_current.last_seen_date, EXCLUDED.last_seen_date),
        last_observed_at = EXCLUDED.last_observed_at, updated_at = CURRENT_TIMESTAMP""", currents)

    _many(conn, """INSERT INTO silver.job_snapshots (series_key, snapshot_date, batch_id, job_no, snapshot_datetime,
        cust_no, area_key, salary_low, salary_high, salary_low_raw, salary_high_raw, appear_date, appear_date_raw,
        apply_cnt, remote_work_type, source_keyword, source_jobcat, source_area, source_page, source_page_size,
        quality_issues, source_platform, native_job_id, source_job_key)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (series_key, snapshot_date, batch_id, job_no) DO NOTHING""", snaps)

    obss = [(skey, sdate, bid, f"yes123:{j['native_job_id']}", o["source_kind"], o["observation_index"],
        o.get("raw_value_min"), o.get("raw_value_max"), o.get("amount_min"), o.get("amount_max"),
        o.get("currency_code"), o.get("currency_basis"), o.get("pay_period"), o.get("range_kind"),
        o.get("compensation_component"), o.get("evidence_text"), o.get("evidence_start"), o.get("evidence_end"),
        o.get("parse_status"), _jb(o.get("quality_flags", [])), o.get("confidence"), o.get("parser_version"))
        for j in jobs for o in j.get("salary_observations", [])]

    if obss:
        _many(conn, """INSERT INTO silver.job_salary_observations (series_key, snapshot_date, batch_id, job_no,
            source_kind, observation_index, raw_value_min, raw_value_max, amount_min, amount_max, currency_code,
            currency_basis, pay_period, range_kind, compensation_component, evidence_text, evidence_start,
            evidence_end, parse_status, quality_flags, confidence, parser_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (series_key, snapshot_date, batch_id, job_no, source_kind, observation_index) DO NOTHING""", obss)

    if ccode:
        row = conn.execute("""SELECT canonical_job_cat_code FROM silver.category_crosswalk
            WHERE source_platform = 'yes123' AND native_category_code = %s AND mapping_status = 'CONFIRMED'""", (ccode,)).fetchone()
        if row and row[0]:
            _many(conn, """INSERT INTO silver.job_category_snapshots (series_key, snapshot_date, batch_id, job_no, job_cat_code)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (series_key, snapshot_date, batch_id, job_no, job_cat_code) DO NOTHING""",
                [(skey, sdate, bid, f"yes123:{j['native_job_id']}", row[0]) for j in jobs])

    return {"batch_id": bid, "status": "loaded-silver-complete", "raw_rows": len(raws), "jobs": len(jobs), "companies": len(comps), "areas": len(areas)}

def ingest_yes123_batches(batches: List[Dict[str, Any]], config: Dict[str, Any], schema_path: Path) -> List[Dict[str, Any]]:
    import psycopg
    from psycopg.types.json import Jsonb
    results = []
    with psycopg.connect(**config) as conn:
        with conn.transaction(): apply_schema(conn, schema_path)
        for b in batches:
            with conn.transaction(): results.append(save_yes123_batch(conn, b, Jsonb))
    return results
