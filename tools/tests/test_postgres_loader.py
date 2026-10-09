import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.platforms.jobwant_104.persistence.loader import normalize_batch, read_batches, summary
from acquisition.platforms.jobwant_104.capture.storage import publish


REQUEST = {"baseUrl": "https://www.104.com.tw/jobs/search/api/jobs", "keyword": "python",
           "area": "6001008007", "jobsource": "index_s", "mode": "s", "order": "15",
           "page": 1, "pagesize": 20}


def job(**changes):
    value = {"jobNo": "J001", "custNo": "C001", "custName": "Example Co",
             "jobName": "Python Engineer", "salaryLow": "50000", "salaryHigh": "80000",
             "appearDate": "20261001", "jobAddrNo": "6001008007", "jobAddrNoDesc": "台北市",
             "jobAddress": "信義區", "lat": "25.033", "lon": "121.5654",
             "coIndustry": "100", "applyCnt": "12", "remoteWorkType": "1",
             "pcSkills": [{"code": "PYTHON", "description": "Python"}], "jobCat": [2007001001],
             "link": {"job": "https://www.104.com.tw/job/abc"}}
    value.update(changes)
    return value


def manifest():
    return {"batchId": "20261005T090000-0123456789ab", "seriesKey": "series-1",
            "snapshotDate": "2026-10-05", "snapshotDateTime": "2026-10-05T09:00:00+08:00",
            "request": REQUEST}


class NormalizeTests(unittest.TestCase):
    def test_identical_duplicates_except_pdd_score_collapse(self):
        rows = [(1, 0, job(pddScore=0.1)), (1, 1, job(pddScore=0.9))]
        normalized = normalize_batch(manifest(), rows)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["appear_date"].isoformat(), "2026-10-01")
        self.assertEqual(normalized[0]["area"]["area_key"], "6001008007|台北市|信義區|25.033|121.5654")
        self.assertEqual(normalized[0]["source_page_size"], 20)

    def test_category_query_filter_is_retained_separately_from_job_category_codes(self):
        request = dict(REQUEST, jobcat="2007000000")
        rows = normalize_batch(dict(manifest(), request=request), [(1, 0, job())])
        self.assertEqual(rows[0]["source_jobcat"], "2007000000")
        self.assertEqual(rows[0]["categories"], [2007001001])

    def test_conflicting_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate"):
            normalize_batch(manifest(), [(1, 0, job()), (1, 1, job(jobName="Different"))])

    def test_bad_nested_json_and_unverified_link_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed pcSkills"):
            normalize_batch(manifest(), [(1, 0, job(pcSkills="not-json"))])
        with self.assertRaisesRegex(ValueError, "Unverified job URL"):
            normalize_batch(manifest(), [(1, 0, job(link={"job": "https://example.com/job"}))])

    def test_non_numeric_fields_are_recorded_as_quality_issues(self):
        row = normalize_batch(manifest(), [(1, 0, job(salaryLow="unknown", applyCnt="1.5"))])[0]
        self.assertIsNone(row["salary_low"])
        self.assertIsNone(row["apply_cnt"])
        self.assertIn("salaryLow:invalid-number", row["quality_issues"])
        self.assertIn("applyCnt:invalid-number", row["quality_issues"])

    def test_location_coordinates_are_checked_without_dropping_the_address(self):
        zero = normalize_batch(manifest(), [(1, 0, job(lat="0", lon="0",
                                                       jobAddress="Address retained"))])[0]
        self.assertIsNone(zero["area"]["latitude"])
        self.assertIsNone(zero["area"]["longitude"])
        self.assertIn("coordinates:zero-zero", zero["quality_issues"])
        self.assertEqual(zero["area"]["job_address"], "Address retained")

        invalid = normalize_batch(manifest(), [(1, 0, job(lat="91", lon="121.5"))])[0]
        self.assertIsNone(invalid["area"]["latitude"])
        self.assertIn("coordinates:out-of-range", invalid["quality_issues"])

    def test_partial_location_fields_are_reported(self):
        row = normalize_batch(manifest(), [(1, 0, job(lon=None, jobAddress=""))])[0]
        self.assertIsNone(row["area"]["latitude"])
        self.assertIsNone(row["area"]["longitude"])
        self.assertIn("coordinates:incomplete", row["quality_issues"])
        self.assertIn("jobAddress:missing", row["quality_issues"])


class LakeReadTests(unittest.TestCase):
    def test_read_batches_verifies_and_reports_every_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            page = {"response": {"data": [job()], "metadata": {"pagination": {
                "currentPage": 1, "lastPage": 1, "count": 1, "total": 1}}},
                "technical": {"httpStatus": 200}}
            publish(Path(folder), REQUEST, [page], "2026-10-05T09:00:00+08:00")
            batches = read_batches(folder)
            self.assertEqual(summary(batches), {"batches": 1, "raw_rows": 1,
                "silver_snapshot_rows": 1, "duplicates_collapsed": 0,
                "pagination_warning_batches": 0, "silver_blocked_batches": 0, "series": 1})
            stored = next(Path(folder).glob("series/*/batches/*/page-00001.json"))
            payload = json.loads(stored.read_text(encoding="utf-8"))
            payload["response"]["data"][0]["jobName"] = "tampered"
            stored.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_batches(folder)

    def test_conflicting_jobs_remain_readable_as_bronze_only(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = {"response": {"data": [job(), job(jobName="Changed")],
                "metadata": {"pagination": {"currentPage": 1, "lastPage": 1, "count": 2, "total": 2}}},
                "technical": {"httpStatus": 200}}
            publish(Path(folder), REQUEST, [payload], "2026-10-05T09:00:00+08:00")
            batches = read_batches(folder)
            self.assertEqual(batches[0]["silver_status"], "BLOCKED")
            self.assertEqual(batches[0]["capture_status"], "SILVER_NORMALIZATION_BLOCKED")
            self.assertEqual(summary(batches)["raw_rows"], 2)
            self.assertEqual(summary(batches)["silver_blocked_batches"], 1)


if __name__ == "__main__":
    unittest.main()
