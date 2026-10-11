"""Audit job category crosswalk coverage and mapping governance."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from ..jobwant_104.persistence.loader import read_db_config


def fetch_crosswalk_audit(config):
    import psycopg

    with psycopg.connect(**config) as conn:
        # 1. Platform & Mapping Status summary
        status_rows = conn.execute("""
            SELECT source_platform,
                   COALESCE(mapping_status, 'UNSPECIFIED') AS status,
                   COUNT(*)::int AS code_count,
                   ROUND(AVG(COALESCE(match_confidence, 0.0))::numeric, 4) AS avg_confidence,
                   MIN(COALESCE(match_confidence, 0.0))::numeric AS min_confidence,
                   MAX(COALESCE(match_confidence, 0.0))::numeric AS max_confidence
            FROM silver.category_crosswalk
            GROUP BY source_platform, mapping_status
            ORDER BY source_platform, status;
        """).fetchall()

        # 2. Canonical target category distribution
        canonical_rows = conn.execute("""
            SELECT c.canonical_job_cat_code,
                   COALESCE(d.job_cat_description, 'UNKNOWN') AS canonical_name,
                   COUNT(*)::int AS mapped_native_codes
            FROM silver.category_crosswalk c
            LEFT JOIN silver.category_dimension d
              ON d.job_cat_code = c.canonical_job_cat_code
            WHERE c.canonical_job_cat_code IS NOT NULL
            GROUP BY c.canonical_job_cat_code, d.job_cat_description
            ORDER BY mapped_native_codes DESC, c.canonical_job_cat_code;
        """).fetchall()

        # 3. Check for pattern collision / underscore wildcard ambiguity
        # Test whether unescaped '2_%' matches any non-standard codes
        collision_check = conn.execute("""
            SELECT native_category_code
            FROM silver.category_crosswalk
            WHERE source_platform = 'yes123'
              AND native_category_code NOT LIKE '2!_%' ESCAPE '!';
        """).fetchall()

        # 4. Inconsistency check: non-confirmed but canonical is populated
        anomalies = conn.execute("""
            SELECT native_category_code, canonical_job_cat_code, mapping_status, match_confidence
            FROM silver.category_crosswalk
            WHERE mapping_status != 'CONFIRMED' AND canonical_job_cat_code IS NOT NULL;
        """).fetchall()

        # 5. Observed jobs coverage in current scope
        job_coverage = conn.execute("""
            WITH job_cats AS (
                SELECT f.job_no,
                       f.source_platform,
                       f.source_jobcat,
                       c.canonical_job_cat_code,
                       c.mapping_status
                FROM gold.pbi_fact_job_scope_v21 f
                LEFT JOIN silver.category_crosswalk c
                  ON c.source_platform = f.source_platform
                 AND c.native_category_code = f.source_jobcat
                WHERE f.source_platform = 'yes123'
            )
            SELECT COUNT(DISTINCT job_no)::int AS total_yes123_jobs,
                   COUNT(DISTINCT CASE WHEN canonical_job_cat_code IS NOT NULL AND mapping_status = 'CONFIRMED' THEN job_no END)::int AS confirmed_mapped_jobs,
                   COUNT(DISTINCT CASE WHEN canonical_job_cat_code IS NULL OR mapping_status != 'CONFIRMED' THEN job_no END)::int AS unconfirmed_or_unmapped_jobs
            FROM job_cats;
        """).fetchone()

        return {
            "statusSummary": [
                {
                    "sourcePlatform": r[0],
                    "mappingStatus": r[1],
                    "codeCount": r[2],
                    "avgConfidence": float(r[3]),
                    "minConfidence": float(r[4]),
                    "maxConfidence": float(r[5]),
                }
                for r in status_rows
            ],
            "totalCrosswalkCodes": sum(r[2] for r in status_rows),
            "canonicalTargets": [
                {
                    "code": r[0],
                    "name": r[1],
                    "nativeCodeCount": r[2],
                }
                for r in canonical_rows
            ],
            "wildcardCollisions": [r[0] for r in collision_check],
            "inconsistentRows": [
                {
                    "nativeCode": r[0],
                    "canonicalCode": r[1],
                    "status": r[2],
                    "confidence": float(r[3]),
                }
                for r in anomalies
            ],
            "observedJobCoverage": {
                "totalYes123Jobs": job_coverage[0] if job_coverage else 0,
                "confirmedMappedJobs": job_coverage[1] if job_coverage else 0,
                "unconfirmedOrUnmappedJobs": job_coverage[2] if job_coverage else 0,
            },
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    cfg = read_db_config(args.env_file)
    audit = fetch_crosswalk_audit(cfg)

    if args.format == "json":
        print(json.dumps(audit, indent=2, ensure_ascii=False))
    else:
        print("=== CATEGORY CROSSWALK AUDIT SUMMARY ===")
        print(f"Total crosswalk native codes: {audit['totalCrosswalkCodes']}")
        print(f"Wildcard collision count: {len(audit['wildcardCollisions'])}")
        print(f"Inconsistent rows (canonical non-null but not confirmed): {len(audit['inconsistentRows'])}")
        for s in audit["statusSummary"]:
            print(f"  Platform: {s['sourcePlatform']}, Status: {s['mappingStatus']}, Count: {s['codeCount']}, AvgConfidence: {s['avgConfidence']:.2f}")
        cov = audit["observedJobCoverage"]
        print(f"Observed yes123 jobs: {cov['totalYes123Jobs']}, Confirmed mapped: {cov['confirmedMappedJobs']}, Unconfirmed: {cov['unconfirmedOrUnmappedJobs']}")
        print(f"Distinct canonical Golden L1 targets: {len(audit['canonicalTargets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
