import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.pagination import collect, validate_page
from acquisition.storage import daily_batches, publish, verify

PROJECT = Path(__file__).resolve().parents[2]
REQUEST = {"baseUrl": "https://www.104.com.tw/jobs/search/api/jobs", "keyword": "powerbi",
           "area": "6001008007,6001008006", "jobsource": "index_s", "mode": "s",
           "order": "15", "page": 1, "pagesize": 20}


def result(page, rows, last=2, total=3):
    return {"response": {"data": [{"jobNo": str(i)} for i in rows],
                         "metadata": {"pagination": {"currentPage": page, "lastPage": last,
                                                     "count": len(rows), "total": total}}},
            "technical": {"httpStatus": 200}}


class PaginationTests(unittest.TestCase):
    def test_saved_real_fixture(self):
        payload = json.loads((PROJECT / "samples/raw/api-response-page-1.sample.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_page(payload, 1)["count"], 20)

    def test_pages_are_requested_once(self):
        calls = []

        def fetch(page):
            calls.append(page)
            return result(page, [1, 2] if page == 1 else [3])

        self.assertEqual(len(collect(fetch)), 2)
        self.assertEqual(calls, [1, 2])

    def test_empty_is_not_an_error_row(self):
        pages = collect(lambda page: result(page, [], last=0, total=0))
        self.assertEqual(pages[0]["response"]["data"], [])

    def test_drift_wrong_page_and_missing_rows_fail(self):
        bad = [result(1, [3]), result(2, [3], total=4), result(2, [])]
        for second in bad:
            with self.subTest(second=second), self.assertRaises(ValueError):
                collect(lambda page: result(1, [1, 2]) if page == 1 else second)

    def test_fractional_metadata_is_rejected(self):
        item = result(1, [1, 2])
        item["response"]["metadata"]["pagination"]["lastPage"] = 2.5
        with self.assertRaises(ValueError):
            validate_page(item["response"], 1)

    def test_total_reconciliation_and_guard(self):
        with self.assertRaises(ValueError):
            collect(lambda p: result(p, [1], last=1, total=2))
        with self.assertRaises(ValueError):
            collect(lambda p: result(p, [1], last=1001, total=1001), max_pages=1000)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.pages = [result(1, [1, 2]), result(2, [3])]

    def test_two_days_and_latest_daily_batch(self):
        first = publish(self.root, REQUEST, self.pages, "2026-08-13T09:00:00+08:00")
        second = publish(self.root, REQUEST, self.pages, "2026-08-13T10:00:00+08:00")
        third = publish(self.root, REQUEST, self.pages, "2026-08-14T09:00:00+08:00")
        selected = daily_batches(self.root, third)
        self.assertEqual([m["batchId"] for m in selected], [second["batchId"], third["batchId"]])
        self.assertTrue((self.root / first["batchPath"] / "manifest.json").exists())

    def test_failure_preserves_current(self):
        publish(self.root, REQUEST, self.pages)
        before = (self.root / "current.json").read_bytes()
        with patch("acquisition.storage.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(OSError):
                publish(self.root, REQUEST, self.pages)
        self.assertEqual((self.root / "current.json").read_bytes(), before)

    def test_bad_batch_cannot_publish(self):
        publish(self.root, REQUEST, self.pages)
        before = (self.root / "current.json").read_bytes()
        bad = copy.deepcopy(self.pages)
        bad[1]["response"]["metadata"]["pagination"]["total"] = 9
        with self.assertRaises(ValueError):
            publish(self.root, REQUEST, bad)
        self.assertEqual((self.root / "current.json").read_bytes(), before)

    def test_checksum_and_path_escape_fail(self):
        manifest = publish(self.root, REQUEST, self.pages)
        page = self.root / manifest["batchPath"] / manifest["pages"][0]["file"]
        page.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify(self.root, manifest)
        manifest["batchPath"] = "../outside"
        with self.assertRaises(ValueError):
            verify(self.root, manifest)


if __name__ == "__main__":
    unittest.main()
