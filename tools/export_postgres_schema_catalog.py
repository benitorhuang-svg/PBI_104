"""Export read-only PostgreSQL schema catalogs under docs/schema/databases."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "docs" / "schema" / "catalog_snapshot.sql"
DATABASE_PATTERN = re.compile(r"^jobwant_[a-z0-9_]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        action="append",
        required=True,
        help="Database to inspect. Repeat for each platform/reporting database.",
    )
    return parser.parse_args()


def export_catalog(database: str, query: bytes, captured_at: str) -> Path:
    if not DATABASE_PATTERN.fullmatch(database):
        raise ValueError(f"Unsupported database name: {database}")

    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-X",
        "-q",
        "-A",
        "-t",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "pbi_admin",
        "-d",
        database,
        "-f",
        "-",
    ]
    result = subprocess.run(command, input=query, capture_output=True, cwd=ROOT)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Catalog query failed for {database}: {detail}")

    catalog = json.loads(result.stdout.decode("utf-8"))
    if catalog.get("database") != database:
        raise RuntimeError(f"Database identity mismatch for {database}")

    target_dir = ROOT / "docs" / "schema" / "databases" / database
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"catalog-{captured_at}.json"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite schema snapshot: {target}")
    target.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    args = parse_args()
    if len(set(args.database)) != len(args.database):
        raise ValueError("Pass each database only once")
    query = QUERY_PATH.read_bytes()
    captured_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for database in args.database:
        target = export_catalog(database, query, captured_at)
        print(target.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
