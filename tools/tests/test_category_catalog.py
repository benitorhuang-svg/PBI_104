import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.category_catalog import (SOURCE_URL, flatten_catalog,
    read_latest_catalog, write_catalog_snapshot)
from capture_category_matrix import (DEFAULT_AREA, category_targets, completed_today,
                                     make_request)


PAYLOAD = [{"no": "2007000000", "des": "資訊軟體系統類", "eng": "IT", "n": [
    {"no": "2007001000", "des": "軟體工程類", "n": [
        {"no": "2007001001", "des": "軟體工程師"}]}]}]


class CategoryCatalogTests(unittest.TestCase):
    def test_flattens_hierarchy_without_losing_parent_or_path(self):
        rows = flatten_catalog(PAYLOAD)
        self.assertEqual([row["depth"] for row in rows], [0, 1, 2])
        self.assertEqual(rows[2]["parent_code"], "2007001000")
        self.assertEqual(rows[2]["path_codes"], ["2007000000", "2007001000", "2007001001"])
        self.assertTrue(rows[2]["is_leaf"])
        roots = category_targets(rows)
        self.assertEqual([row["code"] for row in roots], ["2007000000"])
        self.assertIsNone(DEFAULT_AREA)
        self.assertIsNone(make_request(roots[0], DEFAULT_AREA, 20)["area"])
        level_one = category_targets(rows, depth=1)
        self.assertEqual([row["code"] for row in level_one], ["2007001000"])
        leaves = category_targets(rows, depth=2)
        self.assertEqual([row["code"] for row in leaves], ["2007001001"])
        with self.assertRaisesRegex(ValueError, "depth 2"):
            category_targets(rows, ["2007001000"], depth=2)
        request = make_request(roots[0], "6001008007", 20)
        self.assertEqual(request["jobcat"], "2007000000")
        self.assertNotIn("keyword", request)

    def test_invalid_or_duplicate_categories_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            flatten_catalog([{"no": "1", "des": "A"}, {"no": "1", "des": "B"}])
        with self.assertRaisesRegex(ValueError, "children"):
            flatten_catalog([{"no": "1", "des": "A", "n": {}}])

    def test_resume_does_not_skip_a_page_total_mismatch(self):
        today = datetime.now().astimezone().date().isoformat()
        mismatch = {"snapshotDate": today, "paginationStatus": "PAGE_TOTAL_MISMATCH"}
        request = {"baseUrl": "https://www.104.com.tw/jobs/search/api/jobs",
                   "area": None, "jobsource": "index_s", "mode": "s", "order": "15",
                   "jobcat": "2007000000", "pagesize": 20}
        with patch("capture_category_matrix.daily_batches", return_value=[mismatch]):
            self.assertIsNone(completed_today("data", request))

    def test_resume_skips_a_page_capped_batch(self):
        today = datetime.now().astimezone().date().isoformat()
        capped = {"snapshotDate": today, "paginationStatus": "PAGE_TOTAL_MISMATCH",
                  "paginationDiagnostics": {"pageLimitReached": True}}
        request = {"baseUrl": "https://www.104.com.tw/jobs/search/api/jobs",
                   "area": None, "jobsource": "index_s", "mode": "s", "order": "15",
                   "jobcat": "2007000000", "pagesize": 20}
        with patch("capture_category_matrix.daily_batches", return_value=[capped]):
            self.assertIs(completed_today("data", request), capped)

    def test_catalog_snapshot_is_immutable_and_checksum_verified(self):
        content = json.dumps(PAYLOAD, ensure_ascii=False).encode("utf-8")
        fetched = {"payload": PAYLOAD, "content": content, "rows": flatten_catalog(PAYLOAD),
                   "captured_at": "2026-10-05T09:00:00+08:00"}
        with tempfile.TemporaryDirectory() as folder:
            written = write_catalog_snapshot(folder, fetched)
            loaded = read_latest_catalog(folder)
            self.assertEqual(loaded["manifest"]["sourceUrl"], SOURCE_URL)
            self.assertEqual(loaded["manifest"]["sha256"], written["manifest"]["sha256"])
            data = Path(folder) / "104" / "reference" / "job-categories" / written["manifest"]["file"]
            data.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_latest_catalog(folder)


if __name__ == "__main__":
    unittest.main()
