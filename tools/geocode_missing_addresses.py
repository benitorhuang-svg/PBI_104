"""Backfill missing area coordinates from the local WGS84_TWD97 service."""

import argparse
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from acquisition.shared.geocoding import geocode_candidates, group_candidates, stored_rows
from acquisition.platforms.jobwant_104.persistence.loader import read_db_config


INSERT_SQL = """INSERT INTO silver.address_geocodes
    (area_key, address_hash, normalized_address, input_address, matched_address,
     latitude, longitude, match_level, strategy, canonical_address,
     standardization_version, google_maps_search_url)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (area_key) DO UPDATE SET
      address_hash = EXCLUDED.address_hash,
      normalized_address = EXCLUDED.normalized_address,
      input_address = EXCLUDED.input_address,
      matched_address = EXCLUDED.matched_address,
      latitude = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      match_level = EXCLUDED.match_level,
      strategy = EXCLUDED.strategy,
      canonical_address = EXCLUDED.canonical_address,
      standardization_version = EXCLUDED.standardization_version,
      google_maps_search_url = EXCLUDED.google_maps_search_url,
      geocoded_at = CURRENT_TIMESTAMP"""


def read_candidates(conn, refresh=False):
    rows = conn.execute("""SELECT a.area_key, a.job_addr_no_desc, a.job_address
        FROM silver.area_dimension AS a
        LEFT JOIN silver.address_geocodes AS g USING (area_key)
        WHERE (a.latitude IS NULL OR a.longitude IS NULL)
          AND NULLIF(BTRIM(a.job_address), '') IS NOT NULL
          AND (%s OR g.area_key IS NULL)
        ORDER BY a.area_key""", (refresh,)).fetchall()
    return group_candidates(rows)


def require_schema(conn):
    version = conn.execute("SELECT COALESCE(MAX(version), 0) FROM bronze.schema_migrations").fetchone()[0]
    if version < 7:
        raise RuntimeError("Database schema is older than 7; run sync_lake_to_postgres.py --write first")


def persist_results(conn, candidates, results):
    rows = stored_rows(candidates, results)
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany(INSERT_SQL, rows)
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Ignored local PostgreSQL settings file")
    parser.add_argument("--geocoder-url", default="http://127.0.0.1:3301",
                        help="Base URL for the local WGS84_TWD97 service")
    parser.add_argument("--write", action="store_true", help="Persist validated results to PostgreSQL")
    parser.add_argument("--refresh", action="store_true", help="Re-query previously geocoded missing-coordinate areas")
    args = parser.parse_args(argv)

    try:
        import psycopg

        with psycopg.connect(**read_db_config(args.env_file)) as conn:
            require_schema(conn)
            candidates = read_candidates(conn, args.refresh)
            results = geocode_candidates(args.geocoder_url, candidates)
            counts = {}
            for result in results:
                counts[result["match_level"]] = counts.get(result["match_level"], 0) + 1
            report = {"unique_addresses": len(candidates), "area_variants": sum(len(item["areas"]) for item in candidates),
                      "matches_by_level": counts, "write_requested": args.write}
            if args.write:
                with conn.transaction():
                    report["area_rows_written"] = persist_results(conn, candidates, results)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(f"Address geocode backfill failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
