"""Capture one complete live API batch; Power BI reads the published files."""

import argparse
import json
from pathlib import Path
import sys
import time

TOOLS = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOOLS))

from ..client.embedded_client import client_code, fetch_page
from ..client.pagination import MAX_CAPTURE_PAGES, collect, integer
from .storage import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/104"))
    parser.add_argument("--keyword", default="powerbi")
    parser.add_argument("--area", default="6001008007,6001008006")
    parser.add_argument("--pagesize", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=MAX_CAPTURE_PAGES)
    args = parser.parse_args()
    request = {"baseUrl": "https://www.104.com.tw/jobs/search/api/jobs",
               "keyword": args.keyword, "area": args.area, "jobsource": "index_s",
               "mode": "s", "order": "15", "page": 1,
               "pagesize": integer(args.pagesize, "pagesize", 1)}
    project = TOOLS.parent
    code = client_code(project)
    started = time.monotonic()
    calls = 0

    def fetch(page):
        nonlocal calls
        calls += 1
        return fetch_page(code, request, page)

    try:
        pages = collect(fetch, max_pages=args.max_pages)
        manifest = publish(args.output, request, pages)
    except Exception as error:
        cause = error.__cause__ or error
        response = getattr(cause, "response", None)
        print(json.dumps({"result": "FAIL", "errorType": type(error).__name__,
                          "causeType": type(cause).__name__,
                          "httpStatus": getattr(response, "status_code", None),
                          "httpCalls": calls, "currentPreserved": True}))
        raise SystemExit(1) from None
    print(json.dumps({"result": "PASS", "batchId": manifest["batchId"],
                      "seriesKey": manifest["seriesKey"], "rows": manifest["rows"],
                      "pages": len(pages), "httpCalls": calls,
                      "seconds": round(time.monotonic() - started, 2),
                      "current": str(args.output.resolve() / "current.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
