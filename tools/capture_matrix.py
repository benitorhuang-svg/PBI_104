"""Multi-target acquisition matrix for expanding data sources across keywords and areas."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import time

from acquisition.embedded_client import client_code, fetch_page
from acquisition.pagination import MAX_CAPTURE_PAGES, collect, integer
from acquisition.storage import publish

DEFAULT_TARGETS = [
    {"keyword": "powerbi", "area": "6001008007,6001008006", "pagesize": 20},
    {"keyword": "tableau", "area": "6001008007,6001008006", "pagesize": 20},
    {"keyword": "python", "area": "6001008007,6001008006", "pagesize": 20},
]


def capture_target(code, target, output_dir, max_pages=MAX_CAPTURE_PAGES):
    request = {
        "baseUrl": "https://www.104.com.tw/jobs/search/api/jobs",
        "keyword": target["keyword"],
        "area": target["area"],
        "jobsource": "index_s",
        "mode": "s",
        "order": "15",
        "page": 1,
        "pagesize": integer(target.get("pagesize", 20), "pagesize", 1)
    }
    calls = 0

    def fetch(page):
        nonlocal calls
        calls += 1
        return fetch_page(code, request, page)

    started = time.monotonic()
    pages = collect(fetch, max_pages=max_pages)
    manifest = publish(output_dir, request, pages)
    return {
        "keyword": target["keyword"],
        "area": target["area"],
        "seriesKey": manifest["seriesKey"],
        "batchId": manifest["batchId"],
        "rows": manifest["rows"],
        "pages": len(pages),
        "httpCalls": calls,
        "seconds": round(time.monotonic() - started, 2)
    }


def run_matrix(output_dir=Path("data/104"), targets=None, delay=1.5):
    output_dir = Path(output_dir).resolve()
    targets = targets or DEFAULT_TARGETS
    project = Path(__file__).resolve().parents[1]
    code = client_code(project)
    results = []

    for index, target in enumerate(targets):
        if index > 0 and delay > 0:
            time.sleep(delay)
        try:
            res = capture_target(code, target, output_dir)
            results.append({"status": "PASS", **res})
        except Exception as err:
            results.append({
                "status": "FAIL",
                "keyword": target["keyword"],
                "area": target["area"],
                "error": str(err)
            })

    catalog = {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "totalSeries": len(results),
        "successfulSeries": sum(1 for r in results if r["status"] == "PASS"),
        "totalRows": sum(r.get("rows", 0) for r in results if r["status"] == "PASS"),
        "series": results
    }
    catalog_path = output_dir / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/104"))
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    summary = run_matrix(args.output, delay=args.delay)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
