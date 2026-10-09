"""Capture yes123 live batches and optionally ingest directly into PostgreSQL."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

TOOLS = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOOLS))

from .client import Yes123Client
from .loader import save_yes123_batch
from ..jobwant_104.persistence.loader import read_db_config


def publish_yes123_batch(output_dir: Path, batch: Dict[str, Any]) -> Path:
    """Save immutable JSON batch payload and update latest current pointer."""
    series_dir = output_dir / "series" / batch["series_key"]
    series_dir.mkdir(parents=True, exist_ok=True)
    batch_file = series_dir / f"{batch['batch_id']}.json"

    def default_json(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    content = json.dumps(batch, ensure_ascii=False, indent=2, default=default_json)
    batch_file.write_text(content, encoding="utf-8")

    current_file = output_dir / "current.json"
    current_file.write_text(content, encoding="utf-8")
    return batch_file


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", type=str, default="2_1006_0002_0003",
                        help="yes123 work_mode category code (e.g. 2_1006_0002_0003)")
    parser.add_argument("--keyword", type=str, default=None,
                        help="Search keyword (e.g. 軟體工程師)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Maximum pages to fetch")
    parser.add_argument("--output", type=Path, default=None,
                        help="Optional root path for yes123 batch lake (default: None, direct to DB only)")
    parser.add_argument("--write", action="store_true", default=True,
                        help="Immediately write and promote into PostgreSQL Silver/Gold (default: True)")
    parser.add_argument("--dbname", type=str, default="jobwant_yes123",
                        help="Target PostgreSQL database name (default: jobwant_yes123)")
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Path to environment configuration file")
    args = parser.parse_args(argv)

    if not args.category and not args.keyword:
        print(json.dumps({"result": "FAIL", "error": "Must supply either --category or --keyword"}), file=sys.stderr)
        return 1

    started = time.monotonic()
    client = Yes123Client(min_interval_seconds=2.0)

    try:
        batch = client.collect(
            category_code=args.category,
            keyword=args.keyword,
            max_pages=args.max_pages,
        )
    except Exception as error:
        print(json.dumps({"result": "FAIL", "errorType": type(error).__name__, "message": str(error)}), file=sys.stderr)
        return 1

    batch_path = None
    if args.output:
        batch_path = publish_yes123_batch(args.output, batch)

    ingest_summary = None
    if args.write:
        import psycopg
        from psycopg.types.json import Jsonb

        db_config = read_db_config(args.env_file)
        db_config["dbname"] = args.dbname
        with psycopg.connect(**db_config) as conn:
            with conn.transaction():
                ingest_summary = save_yes123_batch(conn, batch, Jsonb)

    elapsed = round(time.monotonic() - started, 2)
    output = {
        "result": "PASS",
        "platform": "yes123",
        "batchId": batch["batch_id"],
        "seriesKey": batch["series_key"],
        "category": args.category,
        "keyword": args.keyword,
        "reportedTotal": batch["reported_total"],
        "rows": len(batch["jobs"]),
        "pages": len(batch["pages"]),
        "seconds": elapsed,
        "batchFile": str(batch_path) if batch_path else None,
        "databaseIngest": ingest_summary,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
