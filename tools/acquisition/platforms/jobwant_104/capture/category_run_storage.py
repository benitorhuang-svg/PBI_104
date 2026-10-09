"""Persist category-run summaries and locate same-day resume candidates."""

from datetime import datetime
import json
import os

from .storage import daily_batches, series_key


def save_run(output, run_id, summary):
    run_dir = output / "category-runs"
    run_dir.mkdir(exist_ok=True)
    path = run_dir / f"category-run-{run_id}.json"
    temporary = run_dir / ("." + run_id + ".tmp")
    try:
        temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _resumable(item, request):
    return item.get("seriesKey") == series_key(request)


def completed_today(output, request):
    today = datetime.now().astimezone().date().isoformat()
    history = daily_batches(output, {"seriesKey": series_key(request), "request": request})
    return next((item for item in reversed(history)
                 if item["snapshotDate"] == today and _resumable(item, request)), None)
