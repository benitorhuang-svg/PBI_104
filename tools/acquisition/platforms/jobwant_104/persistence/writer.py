"""Transactional PostgreSQL persistence for verified 104 capture batches."""

from datetime import date, datetime

from .pages import backfill_capture_pages, save_capture_pages
from ....shared.postgres_schema import apply_schema
from .raw_payload import (jsonb_projection, normalize_payload,
                          payload_quality_flags, source_json)


def _unique(rows, key):
    values = {}
    for row in rows:
        values[row[key]] = row
    return list(values.values())


def _many(conn, statement, rows):
    values = list(rows)
    if values:
        with conn.cursor() as cursor:
            cursor.executemany(statement, values)


def _save_dimensions(conn, jobs, Jsonb):
    companies = _unique([{"cust_no": row["cust_no"], "company_name": row["company_name"],
                          "co_industry": row["co_industry"],
                          "co_industry_desc": row["co_industry_desc"]} for row in jobs], "cust_no")
    _many(conn, """INSERT INTO silver.company_dimension
        (cust_no, company_name, co_industry, co_industry_desc) VALUES (%s, %s, %s, %s)
        ON CONFLICT (cust_no) DO UPDATE SET
        company_name = COALESCE(EXCLUDED.company_name, silver.company_dimension.company_name),
        co_industry = COALESCE(EXCLUDED.co_industry, silver.company_dimension.co_industry),
        co_industry_desc = COALESCE(EXCLUDED.co_industry_desc, silver.company_dimension.co_industry_desc),
        updated_at = CURRENT_TIMESTAMP""",
        [(r["cust_no"], r["company_name"], r["co_industry"], r["co_industry_desc"])
         for r in companies])

    areas = _unique([row["area"] for row in jobs], "area_key")
    _many(conn, """INSERT INTO silver.area_dimension
        (area_key, job_addr_no, job_addr_no_desc, job_address, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (area_key) DO NOTHING""",
        [(r["area_key"], r["job_addr_no"], r["job_addr_no_desc"], r["job_address"],
          r["latitude"], r["longitude"]) for r in areas])

    skills = _unique([skill for row in jobs for skill in row["skills"]], "skill_code")
    if skills:
        _many(conn, """INSERT INTO silver.skill_dimension (skill_code, skill_description)
            VALUES (%s, %s) ON CONFLICT (skill_code) DO UPDATE SET
            skill_description = COALESCE(EXCLUDED.skill_description, silver.skill_dimension.skill_description)""",
            [(r["skill_code"], r["skill_description"]) for r in skills])

    categories = sorted({code for row in jobs for code in row["categories"]})
    if categories:
        _many(conn, """INSERT INTO silver.category_dimension (job_cat_code)
            VALUES (%s) ON CONFLICT (job_cat_code) DO NOTHING""", [(code,) for code in categories])


def _save_category_catalog(conn, catalog, Jsonb):
    manifest = catalog["manifest"]
    digest = manifest["sha256"]
    captured_at = datetime.fromisoformat(manifest["capturedAt"])
    prior = conn.execute("""SELECT row_count, root_count FROM bronze.job_category_catalogs
        WHERE catalog_sha256 = %s""", (digest,)).fetchone()
    if prior and (prior[0] != len(catalog["rows"]) or prior[1] != len(catalog["payload"])):
        raise ValueError("Database category catalogue conflicts with its content hash")
    conn.execute("""INSERT INTO bronze.job_category_catalogs
        (catalog_sha256, source_url, captured_at, root_count, row_count, payload, manifest)
        VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (catalog_sha256) DO NOTHING""",
        (digest, manifest["sourceUrl"], captured_at, len(catalog["payload"]),
         len(catalog["rows"]), Jsonb(catalog["payload"]), Jsonb(manifest)))
    values = [(digest, row["job_cat_code"],
               int(row["parent_code"]) if row["parent_code"] else None,
               row["name"], row["english_name"], row["depth"], Jsonb(row["path_codes"]),
               row["is_leaf"]) for row in catalog["rows"]]
    _many(conn, """INSERT INTO bronze.job_category_catalog_rows
        (catalog_sha256, job_cat_code, parent_job_cat_code, category_name, english_name,
         hierarchy_depth, path_codes, is_leaf) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (catalog_sha256, job_cat_code) DO NOTHING""", values)
    _many(conn, """INSERT INTO silver.category_dimension
        (job_cat_code, job_cat_description, job_cat_english_name, parent_job_cat_code,
         hierarchy_depth, path_codes, is_leaf, catalog_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_cat_code) DO UPDATE SET
        job_cat_description = EXCLUDED.job_cat_description,
        job_cat_english_name = EXCLUDED.job_cat_english_name,
        parent_job_cat_code = EXCLUDED.parent_job_cat_code,
        hierarchy_depth = EXCLUDED.hierarchy_depth, path_codes = EXCLUDED.path_codes,
        is_leaf = EXCLUDED.is_leaf, catalog_sha256 = EXCLUDED.catalog_sha256""",
        [(row["job_cat_code"], row["name"], row["english_name"],
          int(row["parent_code"]) if row["parent_code"] else None, row["depth"],
          Jsonb(row["path_codes"]), row["is_leaf"], digest) for row in catalog["rows"]])


def _save_current_jobs(conn, jobs, Jsonb):
    sql = """INSERT INTO silver.job_current
        (job_no, cust_no, job_name, description, desc_snippet, area_key, salary_low, salary_high,
         salary_low_raw, salary_high_raw, appear_date, appear_date_raw, apply_cnt, remote_work_type,
         job_link, first_seen_date, last_seen_date, last_observed_at, source_series_key,
         source_keyword, source_jobcat, source_area, quality_issues)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_no) DO UPDATE SET
        cust_no = EXCLUDED.cust_no, job_name = EXCLUDED.job_name, description = EXCLUDED.description,
        desc_snippet = EXCLUDED.desc_snippet, area_key = EXCLUDED.area_key,
        salary_low = EXCLUDED.salary_low, salary_high = EXCLUDED.salary_high,
        salary_low_raw = EXCLUDED.salary_low_raw, salary_high_raw = EXCLUDED.salary_high_raw,
        appear_date = EXCLUDED.appear_date, appear_date_raw = EXCLUDED.appear_date_raw,
        apply_cnt = EXCLUDED.apply_cnt, remote_work_type = EXCLUDED.remote_work_type,
        job_link = EXCLUDED.job_link, first_seen_date = LEAST(silver.job_current.first_seen_date, EXCLUDED.first_seen_date),
        last_seen_date = GREATEST(silver.job_current.last_seen_date, EXCLUDED.last_seen_date),
        last_observed_at = EXCLUDED.last_observed_at, source_series_key = EXCLUDED.source_series_key,
        source_keyword = EXCLUDED.source_keyword, source_jobcat = EXCLUDED.source_jobcat,
        source_area = EXCLUDED.source_area,
        quality_issues = EXCLUDED.quality_issues, updated_at = CURRENT_TIMESTAMP
        WHERE EXCLUDED.last_observed_at >= silver.job_current.last_observed_at"""
    _many(conn, sql, [(
        r["job_no"], r["cust_no"], r["job_name"], r["description"], r["desc_snippet"],
        r["area"]["area_key"], r["salary_low"], r["salary_high"], r["salary_low_raw"],
        r["salary_high_raw"], r["appear_date"], r["appear_date_raw"], r["apply_cnt"],
        r["remote_work_type"], r["job_link"], r["snapshot_date"], r["snapshot_date"],
        r["snapshot_datetime"], r["series_key"], r["source_keyword"], r["source_jobcat"],
        r["source_area"],
        Jsonb(r["quality_issues"])) for r in jobs])


def _save_snapshots(conn, jobs, Jsonb):
    _many(conn, """INSERT INTO silver.job_snapshots
        (series_key, snapshot_date, batch_id, job_no, snapshot_datetime, cust_no, area_key,
         salary_low, salary_high, salary_low_raw, salary_high_raw, appear_date, appear_date_raw,
         apply_cnt, remote_work_type, source_keyword, source_jobcat, source_area, source_page,
         source_page_size, quality_issues)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING""",
        [(r["series_key"], r["snapshot_date"], r["batch_id"], r["job_no"],
          r["snapshot_datetime"], r["cust_no"], r["area"]["area_key"], r["salary_low"],
          r["salary_high"], r["salary_low_raw"], r["salary_high_raw"], r["appear_date"],
          r["appear_date_raw"], r["apply_cnt"], r["remote_work_type"], r["source_keyword"],
          r["source_jobcat"], r["source_area"], r["source_page"], r["source_page_size"],
          Jsonb(r["quality_issues"]))
         for r in jobs])

    skill_rows = {(r["series_key"], r["snapshot_date"], r["batch_id"], r["job_no"],
                   s["skill_code"], s["skill_description"])
                  for r in jobs for s in r["skills"]}
    if skill_rows:
        _many(conn, """INSERT INTO silver.job_skill_snapshots
            (series_key, snapshot_date, batch_id, job_no, skill_code, skill_description)
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""", sorted(skill_rows))

    category_rows = {(r["series_key"], r["snapshot_date"], r["batch_id"], r["job_no"], code)
                     for r in jobs for code in r["categories"]}
    if category_rows:
        _many(conn, """INSERT INTO silver.job_category_snapshots
            (series_key, snapshot_date, batch_id, job_no, job_cat_code)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""", sorted(category_rows))


def _save_salary_observations(conn, jobs, Jsonb):
    rows = [(job["series_key"], job["snapshot_date"], job["batch_id"], job["job_no"],
             item["source_kind"], item["observation_index"], item["raw_value_min"],
             item["raw_value_max"], item["amount_min"], item["amount_max"],
             item["currency_code"], item["currency_basis"], item["pay_period"],
             item["range_kind"], item["compensation_component"], item["evidence_text"],
             item["evidence_start"], item["evidence_end"], item["parse_status"],
             Jsonb(item["quality_flags"]), item["confidence"], item["parser_version"])
            for job in jobs for item in job["salary_observations"]]
    _many(conn, """INSERT INTO silver.job_salary_observations
        (series_key, snapshot_date, batch_id, job_no, source_kind, observation_index,
         raw_value_min, raw_value_max, amount_min, amount_max, currency_code,
         currency_basis, pay_period, range_kind, compensation_component, evidence_text,
         evidence_start, evidence_end, parse_status, quality_flags, confidence, parser_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (series_key, snapshot_date, batch_id, job_no, source_kind, observation_index)
        DO UPDATE SET raw_value_min = EXCLUDED.raw_value_min,
            raw_value_max = EXCLUDED.raw_value_max, amount_min = EXCLUDED.amount_min,
            amount_max = EXCLUDED.amount_max, currency_code = EXCLUDED.currency_code,
            currency_basis = EXCLUDED.currency_basis, pay_period = EXCLUDED.pay_period,
            range_kind = EXCLUDED.range_kind, compensation_component = EXCLUDED.compensation_component,
            evidence_text = EXCLUDED.evidence_text, evidence_start = EXCLUDED.evidence_start,
            evidence_end = EXCLUDED.evidence_end, parse_status = EXCLUDED.parse_status,
            quality_flags = EXCLUDED.quality_flags, confidence = EXCLUDED.confidence,
            parser_version = EXCLUDED.parser_version""", rows)
    description_indexes = [(job["batch_id"], job["job_no"],
                            [item["observation_index"] for item in job["salary_observations"]
                             if item["source_kind"] == "DESCRIPTION"])
                           for job in jobs]
    _many(conn, """DELETE FROM silver.job_salary_observations
        WHERE batch_id = %s AND job_no = %s AND source_kind = 'DESCRIPTION'
          AND NOT (observation_index = ANY(%s::integer[]))""", description_indexes)


def _verify_stored_raw_rows(conn, batch):
    batch_id = batch["manifest"]["batchId"]
    expected = [(page, row_index,
                 jsonb_projection(str(raw.get("jobNo")))
                 if raw.get("jobNo") is not None else None,
                 source_json(raw), payload_quality_flags(raw))
                for page, row_index, raw in batch["raw_rows"]]
    expected.sort(key=lambda row: (row[0], row[1]))
    stored = conn.execute("""SELECT source_page, row_index, job_no,
        payload_source_json, payload, payload_quality_flags
        FROM bronze.raw_job_rows WHERE batch_id = %s ORDER BY source_page, row_index""",
        (batch_id,)).fetchall()
    restored = [(page, row_index, job_no,
                 source if source is not None else source_json(projection), flags)
                for page, row_index, job_no, source, projection, flags in stored]
    if restored != expected:
        raise ValueError(f"Stored Bronze payload differs from verified batch files: {batch_id}")


def _save_batch(conn, batch, Jsonb):
    manifest = batch["manifest"]
    batch_id = manifest["batchId"]
    prior = conn.execute("SELECT manifest_sha256, row_count, capture_status, source_jobcat FROM bronze.capture_batches WHERE batch_id = %s",
                         (batch_id,)).fetchone()
    if prior:
        if (prior[0].strip() != batch["manifest_sha256"]
                or prior[1] != len(batch["raw_rows"])
                or prior[3] != manifest["request"].get("jobcat")):
            raise ValueError(f"Database batch identity conflicts with local manifest: {batch_id}")
        if prior[2] == batch["capture_status"]:
            backfill_capture_pages(conn, batch, Jsonb)
            if prior[2] == "COMPLETE":
                _save_salary_observations(conn, batch["jobs"], Jsonb)
            return {"batch_id": batch_id, "status": "already-loaded"}
        safe_reclassifications = {
            "SILVER_NORMALIZATION_BLOCKED": {"COMPLETE"},
            "PAGE_TOTAL_MISMATCH_AND_SILVER_NORMALIZATION_BLOCKED": {"PAGE_TOTAL_MISMATCH"}}
        if batch["capture_status"] not in safe_reclassifications.get(prior[2], set()):
            raise ValueError(f"Database batch status conflicts with local manifest: {batch_id}")
        _verify_stored_raw_rows(conn, batch)
        updated = conn.execute("""UPDATE bronze.capture_batches SET capture_status = %s
            WHERE batch_id = %s AND capture_status = %s""",
            (batch["capture_status"], batch_id, prior[2]))
        if updated.rowcount != 1:
            raise ValueError(f"Database batch status changed during reclassification: {batch_id}")
        if batch["capture_status"] == "COMPLETE":
            jobs = batch["jobs"]
            _save_dimensions(conn, jobs, Jsonb)
            _save_current_jobs(conn, jobs, Jsonb)
            _save_snapshots(conn, jobs, Jsonb)
            _save_salary_observations(conn, jobs, Jsonb)
            return {"batch_id": batch_id, "status": "promoted-to-silver",
                    "raw_rows": len(batch["raw_rows"]), "snapshot_jobs": len(jobs)}
        return {"batch_id": batch_id, "status": "reclassified-bronze-only",
                "capture_status": batch["capture_status"]}

    request = manifest["request"]
    snapshot_date = date.fromisoformat(manifest["snapshotDate"])
    snapshot_time = datetime.fromisoformat(manifest["snapshotDateTime"])
    conn.execute("""INSERT INTO bronze.capture_batches
        (batch_id, series_key, snapshot_date, snapshot_datetime, source_jobcat, request,
         manifest_sha256, manifest, row_count, capture_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (batch_id, manifest["seriesKey"], snapshot_date, snapshot_time,
         request.get("jobcat"), Jsonb(request),
         batch["manifest_sha256"], Jsonb(manifest), len(batch["raw_rows"]), batch["capture_status"]))
    raw_values = []
    for page, row_index, raw in batch["raw_rows"]:
        payload, flags = normalize_payload(raw)
        job_no = (jsonb_projection(str(raw.get("jobNo")))
                  if raw.get("jobNo") is not None else None)
        raw_values.append((batch_id, page, row_index, job_no,
                           Jsonb(payload), source_json(raw), Jsonb(flags)))
    if raw_values:
        _many(conn, """INSERT INTO bronze.raw_job_rows
            (batch_id, source_page, row_index, job_no, payload,
             payload_source_json, payload_quality_flags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""", raw_values)
    save_capture_pages(conn, batch_id, batch.get("capture_pages", []), Jsonb)
    jobs = batch["jobs"]
    if batch["capture_status"] == "COMPLETE":
        _save_dimensions(conn, jobs, Jsonb)
        _save_current_jobs(conn, jobs, Jsonb)
        _save_snapshots(conn, jobs, Jsonb)
        _save_salary_observations(conn, jobs, Jsonb)
    status = "loaded" if batch["capture_status"] == "COMPLETE" else "loaded-bronze-only"
    return {"batch_id": batch_id, "status": status, "raw_rows": len(raw_values),
            "snapshot_jobs": len(jobs), "capture_status": batch["capture_status"]}


def ingest_batches(batches, config, schema_path, category_catalog=None):
    """Apply schema, then commit each immutable batch atomically and idempotently."""
    import psycopg
    from psycopg.types.json import Jsonb

    results = []
    with psycopg.connect(**config) as conn:
        with conn.transaction():
            apply_schema(conn, schema_path)
            if category_catalog:
                _save_category_catalog(conn, category_catalog, Jsonb)
        for batch in batches:
            with conn.transaction():
                results.append(_save_batch(conn, batch, Jsonb))
    return results
