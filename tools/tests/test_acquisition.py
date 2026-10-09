import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.platforms.jobwant_104.client.pagination import PaginationTotalMismatch, collect, validate_page
from acquisition.platforms.jobwant_104.capture.storage import daily_batches, publish, series_key, verify

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
        payload = json.loads((PROJECT / "tools/tests/fixtures/api-response-page-1.fixture.json").read_text(encoding="utf-8"))
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
            collect(lambda p: result(p, [1], last=151, total=151), max_pages=151)

    def test_page_cap_fetches_only_the_allowed_pages_and_marks_incomplete(self):
        calls = []

        def fetch(page):
            calls.append(page)
            return result(page, [page * 2 - 1, page * 2], last=3, total=5)

        with self.assertRaises(PaginationTotalMismatch) as raised:
            collect(fetch, max_pages=2)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(len(raised.exception.pages), 2)
        self.assertTrue(raised.exception.diagnostics["pageLimitReached"])
        self.assertEqual(raised.exception.diagnostics["configuredPageLimit"], 2)

    def test_page_cap_cannot_be_raised_above_150(self):
        calls = []
        with self.assertRaisesRegex(ValueError, "max_pages must be <= 150"):
            collect(lambda page: calls.append(page), max_pages=151)
        self.assertEqual(calls, [])

    def test_total_mismatch_reports_duplicate_job_counts_without_payloads(self):
        with self.assertRaises(PaginationTotalMismatch) as raised:
            collect(lambda page: result(1, [7, 7], last=1, total=1))
        self.assertEqual(raised.exception.diagnostics["uniqueJobNos"], 1)
        self.assertEqual(raised.exception.diagnostics["duplicateJobNoRows"], 1)
        self.assertEqual(raised.exception.diagnostics["delta"], 1)


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

    def test_histories_remain_separate_by_query_series(self):
        first = publish(self.root, REQUEST, self.pages, "2026-08-13T09:00:00+08:00")
        other_request = dict(REQUEST, keyword="tableau")
        second = publish(self.root, other_request, self.pages, "2026-08-13T10:00:00+08:00")
        self.assertNotEqual(first["seriesKey"], second["seriesKey"])
        self.assertEqual([batch["seriesKey"] for batch in daily_batches(self.root, first)], [first["seriesKey"]])
        self.assertEqual([batch["seriesKey"] for batch in daily_batches(self.root, second)], [second["seriesKey"]])

    def test_keyword_series_identity_is_unchanged_and_category_only_is_supported(self):
        legacy = {key: REQUEST[key] for key in ("baseUrl", "area", "jobsource", "mode", "order", "keyword")}
        old_key = __import__("hashlib").sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest()[:20]
        self.assertEqual(series_key(REQUEST), old_key)
        category_request = {key: value for key, value in REQUEST.items() if key != "keyword"}
        category_request["jobcat"] = "2007000000"
        self.assertNotEqual(series_key(category_request), old_key)
        with self.assertRaisesRegex(ValueError, "keyword or jobcat"):
            series_key({key: value for key, value in REQUEST.items() if key != "keyword"})

    def test_category_batch_does_not_replace_keyword_current_pointer(self):
        publish(self.root, REQUEST, self.pages)
        before = (self.root / "current.json").read_bytes()
        category_request = {key: value for key, value in REQUEST.items() if key != "keyword"}
        category_request["jobcat"] = "2007000000"
        category = publish(self.root, category_request, self.pages, update_current=False)
        self.assertTrue((self.root / category["batchPath"] / "manifest.json").exists())
        self.assertEqual((self.root / "current.json").read_bytes(), before)

    def test_total_mismatch_is_stored_only_with_explicit_page_diagnostics(self):
        pages = [result(1, [1, 2], last=2, total=2), result(2, [3], last=2, total=2)]
        with self.assertRaises(PaginationTotalMismatch) as raised:
            collect(lambda page: pages[page - 1])
        error = raised.exception
        with self.assertRaisesRegex(ValueError, "API total"):
            publish(self.root, REQUEST, error.pages)
        manifest = publish(self.root, REQUEST, error.pages,
                           pagination_status="PAGE_TOTAL_MISMATCH",
                           pagination_diagnostics=error.diagnostics,
                           update_current=False)
        self.assertEqual(verify(self.root, manifest), 3)
        self.assertEqual(manifest["paginationStatus"], "PAGE_TOTAL_MISMATCH")

    def test_page_capped_batch_is_verifiable_but_incomplete(self):
        with self.assertRaises(PaginationTotalMismatch) as raised:
            collect(lambda page: result(page, [page * 2 - 1, page * 2], last=3, total=5),
                    max_pages=2)
        error = raised.exception
        manifest = publish(self.root, REQUEST, error.pages,
                           pagination_status="PAGE_TOTAL_MISMATCH",
                           pagination_diagnostics=error.diagnostics,
                           update_current=False)
        self.assertEqual(verify(self.root, manifest), 4)
        self.assertTrue(manifest["paginationDiagnostics"]["pageLimitReached"])

    def test_failure_preserves_current(self):
        publish(self.root, REQUEST, self.pages)
        before = (self.root / "current.json").read_bytes()
        with patch("acquisition.platforms.jobwant_104.capture.storage.os.replace", side_effect=OSError("simulated")):
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
