import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.postgres_capture import (CaptureSink, DatabaseCaptureError,
                                           build_batch, resume_compatible)
from acquisition.storage import series_key


REQUEST = {"baseUrl": "https://www.104.com.tw/jobs/search/api/jobs",
           "jobcat": "2007001001", "area": None, "jobsource": "index_s",
           "mode": "s", "order": "15", "page": 1, "pagesize": 30}


def job(**changes):
    value = {"jobNo": "J001", "custNo": "C001", "custName": "Example Co",
             "jobName": "Python Engineer", "salaryLow": "50000", "salaryHigh": "80000",
             "appearDate": "20261001", "jobAddrNo": "6001008007",
             "jobAddrNoDesc": "台北市", "jobAddress": "信義區", "lat": "25.033",
             "lon": "121.5654", "coIndustry": "100", "applyCnt": "12",
             "remoteWorkType": "1", "pcSkills": [{"code": "PYTHON",
                                                     "description": "Python"}],
             "jobCat": [2007001001],
             "link": {"job": "https://www.104.com.tw/job/abc"}}
    value.update(changes)
    return value


def page(rows, total=None):
    count = len(rows)
    return {"response": {"data": rows, "metadata": {"pagination": {
        "currentPage": 1, "lastPage": 1, "count": count,
        "total": count if total is None else total}}},
        "technical": {"httpStatus": 200}}


class FakeTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.active = True
        return self

    def __exit__(self, error_type, error, traceback):
        self.connection.active = False
        if error_type:
            self.connection.rollbacks += 1
        else:
            self.connection.commits += 1
        return False


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.active = False
        self.commits = 0
        self.rollbacks = 0
        self.rows = []
        self.parameters = None
        self.query_error = None

    def transaction(self):
        return FakeTransaction(self)

    def execute(self, query, parameters):
        if not self.active:
            raise AssertionError("Database lookup must use a transaction")
        if self.query_error:
            raise self.query_error
        self.parameters = parameters
        return FakeResult(self.rows)


class DirectCaptureTests(unittest.TestCase):
    def test_complete_batch_is_silver_eligible(self):
        batch = build_batch(REQUEST, [page([job()])],
                           acquired_at="2026-10-06T09:00:00+08:00")
        self.assertEqual(batch["capture_status"], "COMPLETE")
        self.assertEqual(batch["silver_status"], "PASS")
        self.assertEqual(len(batch["capture_pages"]), 1)
        self.assertEqual(batch["raw_rows"][0][2]["jobNo"], "J001")

    def test_page_mismatch_stays_incomplete_even_when_normalization_passes(self):
        batch = build_batch(REQUEST, [page([job()], total=2)],
                            pagination_status="PAGE_TOTAL_MISMATCH",
                            diagnostics={"pageLimitReached": False},
                            acquired_at="2026-10-06T09:00:00+08:00")
        self.assertEqual(batch["capture_status"], "PAGE_TOTAL_MISMATCH")
        self.assertEqual(batch["manifest"]["paginationDiagnostics"]["pageLimitReached"], False)

    def test_conflicting_duplicate_blocks_silver_and_remains_bronze(self):
        batch = build_batch(REQUEST, [page([job(), job(jobName="Different")])],
                            acquired_at="2026-10-06T09:00:00+08:00")
        self.assertEqual(batch["capture_status"], "SILVER_NORMALIZATION_BLOCKED")
        self.assertEqual(batch["silver_status"], "BLOCKED")
        self.assertEqual(batch["jobs"], [])
        self.assertEqual(len(batch["raw_rows"]), 2)

    def test_database_write_runs_inside_category_transaction(self):
        connection = FakeConnection()
        sink = CaptureSink(connection, lambda value: value)
        with patch("acquisition.postgres_capture._save_batch",
                   side_effect=lambda *args: self.assertTrue(connection.active) or {"status": "loaded"}):
            self.assertEqual(sink.save({"manifest": {}}), {"status": "loaded"})
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)

    def test_database_write_error_rolls_back_category_transaction(self):
        connection = FakeConnection()
        sink = CaptureSink(connection, lambda value: value)
        with patch("acquisition.postgres_capture._save_batch", side_effect=ValueError("write failed")):
            with self.assertRaisesRegex(DatabaseCaptureError, "Category transaction failed"):
                sink.save({"manifest": {}})
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_resume_lookup_accepts_matching_warning_batch_and_date(self):
        connection = FakeConnection()
        batch = ("batch-1", {"seriesKey": series_key(REQUEST)}, 4,
                 "PAGE_TOTAL_MISMATCH")
        connection.rows = [batch]
        sink = CaptureSink(connection, lambda value: value)
        self.assertEqual(sink.existing_today(REQUEST, "2026-10-06"), batch)
        self.assertEqual(connection.parameters,
                         ("2026-10-06", REQUEST["jobcat"], series_key(REQUEST)))
        self.assertEqual(connection.commits, 1)

    def test_resume_lookup_failure_rolls_back_and_is_reported(self):
        connection = FakeConnection()
        connection.query_error = ValueError("lookup failed")
        sink = CaptureSink(connection, lambda value: value)
        with self.assertRaisesRegex(DatabaseCaptureError, "resume lookup failed"):
            sink.existing_today(REQUEST, "2026-10-06")
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_resume_requires_the_same_query_series(self):
        other = dict(REQUEST, pagesize=20)
        self.assertTrue(resume_compatible({"seriesKey": series_key(other)}, other))
        another_category = dict(REQUEST, jobcat="2007001002")
        self.assertFalse(resume_compatible(
            {"seriesKey": series_key(another_category)}, REQUEST))


if __name__ == "__main__":
    unittest.main()
