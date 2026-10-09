"""Validate immutable capture batches and load them into local PostgreSQL."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path

from ..capture.storage import verify
from ....shared.salary_parser import extract_salary_observations
from .raw_payload import payload_quality_flags


def clean_text(value):
    if value is None:
        return None
    if isinstance(value, (dict, list, bool)):
        raise ValueError("Expected a text or numeric scalar")
    text = "".join(char for char in str(value) if ord(char) >= 32).strip()
    return text or None


def number(value, field, issues, integer=False):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or (integer and result != result.to_integral_value()):
            raise InvalidOperation
        return int(result) if integer else result
    except (InvalidOperation, ValueError):
        issues.append(f"{field}:invalid-number")
        return None


def array_value(value, field):
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"Malformed {field} JSON") from error
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON array")
    return value


def area_record(job, issues):
    addr_no = number(job.get("jobAddrNo"), "jobAddrNo", issues, integer=True)
    latitude = number(job.get("lat"), "lat", issues)
    longitude = number(job.get("lon"), "lon", issues)
    has_latitude = job.get("lat") not in (None, "")
    has_longitude = job.get("lon") not in (None, "")
    if latitude is not None and longitude is not None:
        if not Decimal(-90) <= latitude <= Decimal(90) or not Decimal(-180) <= longitude <= Decimal(180):
            issues.append("coordinates:out-of-range")
            latitude = longitude = None
        elif latitude == 0 and longitude == 0:
            issues.append("coordinates:zero-zero")
            latitude = longitude = None
    else:
        issues.append("coordinates:incomplete" if has_latitude or has_longitude
                      else "coordinates:missing")
        latitude = longitude = None
    description = clean_text(job.get("jobAddrNoDesc"))
    address = clean_text(job.get("jobAddress"))
    if not address:
        issues.append("jobAddress:missing")
    components = ["" if addr_no is None else str(addr_no), description or "", address or "",
                  "" if latitude is None else format(latitude.normalize(), "g"),
                  "" if longitude is None else format(longitude.normalize(), "g")]
    key = "|".join(components)
    return {"area_key": key, "job_addr_no": addr_no, "job_addr_no_desc": description,
            "job_address": address, "latitude": latitude, "longitude": longitude}


def job_link(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("Malformed link JSON") from error
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("link must be an object")
    url = clean_text(value.get("job"))
    if url and not url.startswith("https://www.104.com.tw/"):
        raise ValueError("Unverified job URL; original payload is retained")
    return url


def normalize_batch(manifest, raw_rows):
    if any(payload_quality_flags(raw) for _, _, raw in raw_rows):
        raise ValueError("Source payload needs a lossy PostgreSQL-safe projection")
    unique = {}
    for page, row_index, raw in raw_rows:
        job_no = clean_text(raw.get("jobNo"))
        if not job_no or not clean_text(raw.get("custNo")):
            raise ValueError("jobNo and custNo must be present before Silver load")
        variant = dict(raw)
        variant.pop("pddScore", None)
        variant.pop("interactionRecord", None)
        previous = unique.get(job_no)
        if previous and previous[0] != variant:
            raise ValueError(f"Conflicting duplicate jobNo in batch: {job_no}")
        unique.setdefault(job_no, (variant, page, row_index, raw))

    request = manifest["request"]
    snapshot_date = date.fromisoformat(manifest["snapshotDate"])
    snapshot_datetime = datetime.fromisoformat(manifest["snapshotDateTime"])
    jobs = []
    for job_no, (_, page, _, raw) in sorted(unique.items()):
        issues = []
        cust_no = clean_text(raw.get("custNo"))
        area = area_record(raw, issues)
        salary_low = number(raw.get("salaryLow"), "salaryLow", issues)
        salary_high = number(raw.get("salaryHigh"), "salaryHigh", issues)
        appear_raw = clean_text(raw.get("appearDate"))
        try:
            appear_date = datetime.strptime(appear_raw, "%Y%m%d").date() if appear_raw else None
        except ValueError:
            appear_date = None
            issues.append("appearDate:invalid")
        co_industry = number(raw.get("coIndustry"), "coIndustry", issues, integer=True)
        apply_count = number(raw.get("applyCnt"), "applyCnt", issues, integer=True)
        remote_type = number(raw.get("remoteWorkType"), "remoteWorkType", issues, integer=True)
        skills = []
        for item in array_value(raw.get("pcSkills"), "pcSkills"):
            if not isinstance(item, dict) or not clean_text(item.get("code")):
                raise ValueError(f"Every pcSkills item needs a code (jobNo {job_no})")
            skills.append({"skill_code": clean_text(item["code"]),
                           "skill_description": clean_text(item.get("description"))})
        categories = []
        for item in array_value(raw.get("jobCat"), "jobCat"):
            code = number(item, "jobCat", issues, integer=True)
            if code is None:
                raise ValueError(f"Invalid jobCat code (jobNo {job_no})")
            categories.append(code)
        page_size = number(request.get("pagesize"), "pagesize", issues, integer=True)
        if page_size is None:
            raise ValueError("Request pagesize is required before Silver load")
        row = {
            "job_no": job_no, "cust_no": cust_no,
            "job_name": clean_text(raw.get("jobName")),
            "description": clean_text(raw.get("description")),
            "desc_snippet": clean_text(raw.get("descSnippet")), "area": area,
            "salary_low": salary_low, "salary_high": salary_high,
            "salary_low_raw": clean_text(raw.get("salaryLow")),
            "salary_high_raw": clean_text(raw.get("salaryHigh")),
            "salary_observations": extract_salary_observations(
                raw.get("salaryLow"), raw.get("salaryHigh"), clean_text(raw.get("description"))),
            "appear_date": appear_date, "appear_date_raw": appear_raw,
            "apply_cnt": apply_count, "remote_work_type": remote_type,
            "job_link": job_link(raw.get("link")),
            "co_industry": co_industry,
            "co_industry_desc": clean_text(raw.get("coIndustryDesc")),
            "company_name": clean_text(raw.get("custName")),
            "snapshot_date": snapshot_date, "snapshot_datetime": snapshot_datetime,
            "series_key": manifest["seriesKey"], "batch_id": manifest["batchId"],
            "source_keyword": clean_text(request.get("keyword")),
            "source_jobcat": clean_text(request.get("jobcat")),
            "source_area": clean_text(request.get("area")),
            "source_page": page, "source_page_size": page_size,
            "quality_issues": issues, "skills": skills, "categories": sorted(set(categories))
        }
        jobs.append(row)
    return jobs


def read_batches(data_root):
    root = Path(data_root).resolve()
    lake = root if (root / "series").is_dir() or (root / "categories").is_dir() else root / "104"
    if not lake.is_dir():
        raise FileNotFoundError(f"No immutable batch lake under {root}")
    batches = []
    manifest_paths = set((lake / "series").glob("*/batches/*/manifest.json"))
    manifest_paths.update((lake / "categories").glob("*/batches/*/manifest.json"))
    for path in sorted(manifest_paths):
        content = path.read_bytes()
        manifest = json.loads(content)
        verify(lake, manifest)
        expected = (lake / manifest["batchPath"]).resolve()
        if expected != path.parent.resolve():
            raise ValueError(f"Manifest path does not match its directory: {path}")
        raw_rows, capture_pages = [], []
        for page in manifest["pages"]:
            data = json.loads((path.parent / page["file"]).read_text(encoding="utf-8"))
            capture_pages.append({"source_page": page["page"],
                                  "response_sha256": page["sha256"],
                                  "row_count": page["rows"],
                                  "response_metadata": data["response"]["metadata"],
                                  "technical_metadata": data["technical"]})
            for row_index, payload in enumerate(data["response"]["data"]):
                raw_rows.append((page["page"], row_index, payload))
        if len(raw_rows) != manifest["rows"]:
            raise ValueError(f"Raw row count mismatch: {path}")
        try:
            jobs = normalize_batch(manifest, raw_rows)
            silver_status, silver_error_type = "PASS", None
        except (TypeError, ValueError) as error:
            jobs, silver_status, silver_error_type = [], "BLOCKED", type(error).__name__
        pagination_status = manifest.get("paginationStatus", "PASS")
        if pagination_status not in ("PASS", "PAGE_TOTAL_MISMATCH"):
            raise ValueError(f"Unsupported pagination status in {path}")
        issues = []
        if pagination_status != "PASS":
            issues.append("PAGE_TOTAL_MISMATCH")
        if silver_status != "PASS":
            issues.append("SILVER_NORMALIZATION_BLOCKED")
        capture_status = "_AND_".join(issues) if issues else "COMPLETE"
        batches.append({"manifest": manifest, "manifest_sha256": hashlib.sha256(content).hexdigest(),
                        "raw_rows": raw_rows, "jobs": jobs, "capture_pages": capture_pages,
                        "silver_status": silver_status,
                        "silver_error_type": silver_error_type, "capture_status": capture_status,
                        "pagination_status": pagination_status})
    if not batches:
        raise ValueError(f"No batch manifests found under {lake / 'series'} or {lake / 'categories'}")
    ids = [item["manifest"]["batchId"] for item in batches]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate batchId found in local lake")
    return sorted(batches, key=lambda item: (item["manifest"]["snapshotDateTime"],
                                             item["manifest"]["batchId"]))


def summary(batches):
    ready = [batch for batch in batches if batch["capture_status"] == "COMPLETE"]
    return {"batches": len(batches), "raw_rows": sum(len(b["raw_rows"]) for b in batches),
            "silver_snapshot_rows": sum(len(b["jobs"]) for b in ready),
            "duplicates_collapsed": sum(len(b["raw_rows"]) - len(b["jobs"]) for b in ready),
            "pagination_warning_batches": sum(b["pagination_status"] != "PASS" for b in batches),
            "silver_blocked_batches": len(batches) - len(ready),
            "series": len({b["manifest"]["seriesKey"] for b in batches})}


def read_db_config(env_file):
    values = {}
    path = Path(env_file)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("PBI104_POSTGRES_DB", "PBI104_POSTGRES_USER", "PBI104_POSTGRES_PASSWORD",
                "PBI104_POSTGRES_HOST", "PBI104_POSTGRES_PORT"):
        if os.getenv(key) is not None:
            values[key] = os.environ[key]
    if not values.get("PBI104_POSTGRES_PASSWORD"):
        raise ValueError("Set PBI104_POSTGRES_PASSWORD in the ignored .env file")
    return {"dbname": values.get("PBI104_POSTGRES_DB", "jobwant_104"),
            "user": values.get("PBI104_POSTGRES_USER", "pbi_admin"),
            "password": values["PBI104_POSTGRES_PASSWORD"],
            "host": values.get("PBI104_POSTGRES_HOST", "127.0.0.1"),
            "port": int(values.get("PBI104_POSTGRES_PORT", "5433"))}
