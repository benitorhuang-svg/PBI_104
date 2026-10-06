"""Validate saved 104 captures and optionally ingest them into local PostgreSQL."""

import argparse
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from acquisition.postgres_loader import read_batches, read_db_config, summary
from acquisition.postgres_writer import ingest_batches
from acquisition.category_catalog import read_latest_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"),
                        help="Root containing the immutable data/104 batch lake")
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Ignored local PostgreSQL settings file")
    parser.add_argument("--write", action="store_true",
                        help="Apply the schema and transactionally import verified batches")
    args = parser.parse_args(argv)

    try:
        batches = read_batches(args.data_root)
        category_catalog = read_latest_catalog(args.data_root)
        report = summary(batches)
        report["category_catalog_rows"] = len(category_catalog["rows"]) if category_catalog else 0
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not batches and not category_catalog:
            raise FileNotFoundError("No capture batches or official category catalogue were found")
        if not args.write:
            print("Dry run only; PostgreSQL was not contacted. Pass --write to import.")
            return 0

        config = read_db_config(args.env_file)
        schema = TOOLS / "sql" / "init_postgres_schema.sql"
        results = ingest_batches(batches, config, schema, category_catalog)
        loaded = sum(item["status"] == "loaded" for item in results)
        promoted = sum(item["status"] == "promoted-to-silver" for item in results)
        bronze_only = sum(item["status"] == "loaded-bronze-only" for item in results)
        reclassified = sum(item["status"] == "reclassified-bronze-only" for item in results)
        skipped = sum(item["status"] == "already-loaded" for item in results)
        category_count = len(category_catalog["rows"]) if category_catalog else 0
        print(f"PostgreSQL import complete: {loaded} new batches, {promoted} promoted to Silver, "
              f"{bronze_only} new Bronze-only batches, {reclassified} Bronze status updates, "
              f"{skipped} already loaded, {category_count} official categories.")
        return 0
    except Exception as error:
        print(f"PostgreSQL sync failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
