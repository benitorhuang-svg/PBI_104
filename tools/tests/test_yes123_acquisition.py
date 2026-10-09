from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.platforms.yes123.client import (
    Yes123Client,
    compute_series_key,
    extract_reported_total,
    parse_job_cards,
    is_taiwan_location,
    parse_job_detail_dom,
)
from acquisition.platforms.yes123.loader import (
    clean_text,
    normalize_company_name,
    parse_date_str,
    save_yes123_batch,
)

SAMPLE_HTML = """<!DOCTYPE html><html><head>
    <meta name="description" content="想找軟體工程師工作，yes123工作查詢提供2個工作機會:軟體工程師-三井科技、[AI]工程師-英業達。" />
</head><body>
    <div class="Job_opening_item">
        <div class="Job_opening_item_title"><a href="/admin/job.asp?p_id=C001&job_id=J001">軟體工程師</a></div>
        <a href="/admin/comp_info.asp?p_id=C001">三井科技股份有限公司</a>
        <div class="Job_opening_item_title_payment">月薪　50,000 至 70,000元</div>
        <div class="Job_opening_item_date">10.09</div>
        <span>台北市松山區</span><span>全職</span>
    </div>
    <div class="Job_opening_item">
        <div class="Job_opening_item_title"><a href="/admin/job.asp?p_id=C002&job_id=J002">[AI]工程師</a></div>
        <a href="/admin/comp_info.asp?p_id=C002">英業達股份有限公司</a>
        <div class="Job_opening_item_title_payment">薪資面議(經常性薪資達4萬元含以上)</div>
        <div class="Job_opening_item_date">10.09</div>
        <span>桃園市大溪區</span><span>全職</span>
    </div>
    <div class="Job_opening_item"><div>廣告版位</div></div>
</body></html>"""


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def executemany(self, statement, rows):
        self.connection.executed.append((statement, rows))


class FakeConnection:
    def __init__(self):
        self.executed = []

    def cursor(self):
        return FakeCursor(self)

    def execute(self, statement, parameters=None):
        self.executed.append((statement, parameters))

        class Result:
            def fetchone(self):
                # Return canonical category code for crosswalk query
                return (2007001001,)

        return Result()


class Yes123AcquisitionTests(unittest.TestCase):
    def test_compute_series_key_deterministic(self):
        req1 = {"category_code": "2_1006_0002_0003"}
        req2 = {"category_code": "2_1006_0002_0003"}
        self.assertEqual(compute_series_key(req1), compute_series_key(req2))
        self.assertEqual(len(compute_series_key(req1)), 20)

        with self.assertRaises(ValueError):
            compute_series_key({})

    def test_extract_reported_total(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        total = extract_reported_total(soup)
        self.assertEqual(total, 2)

    def test_parse_job_cards(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        jobs = parse_job_cards(soup)
        self.assertEqual(len(jobs), 2)

        j1 = jobs[0]
        self.assertEqual(j1["native_job_id"], "J001")
        self.assertEqual(j1["native_company_id"], "C001")
        self.assertEqual(j1["source_job_key"], "yes123:J001")
        self.assertEqual(j1["source_company_key"], "yes123:C001")
        self.assertEqual(j1["job_title"], "軟體工程師")
        self.assertEqual(j1["company_name"], "三井科技股份有限公司")
        self.assertEqual(j1["raw_salary"], "月薪　50,000 至 70,000元")
        self.assertEqual(j1["raw_area"], "台北市松山區")
        self.assertEqual(j1["standardized_address"], "臺北市松山區")
        self.assertEqual(j1["job_url"], "https://www.yes123.com.tw/wk_index/job.asp?p_id=C001&job_id=J001")

        # Verify salary observation
        obs = j1["salary_observations"]
        self.assertTrue(len(obs) >= 1)
        desc_obs = [o for o in obs if o["source_kind"] == "DESCRIPTION"]
        self.assertEqual(desc_obs[0]["amount_min"], 50000)
        self.assertEqual(desc_obs[0]["amount_max"], 70000)
        self.assertEqual(desc_obs[0]["pay_period"], "MONTH")

    def test_client_collect_mocked(self):
        client = Yes123Client(min_interval_seconds=0.0)
        client.fetch_page = MagicMock(return_value=(200, SAMPLE_HTML.encode("utf-8"), parse_job_cards(BeautifulSoup(SAMPLE_HTML, "html.parser")), 2))

        batch = client.collect(category_code="2_1006_0002_0003", max_pages=1)
        self.assertEqual(batch["manifest"]["sourcePlatform"], "yes123")
        self.assertEqual(batch["manifest"]["rows"], 2)
        self.assertEqual(batch["reported_total"], 2)
        self.assertEqual(len(batch["jobs"]), 2)
        self.assertEqual(len(batch["raw_rows"]), 2)
        self.assertTrue(batch["manifest_sha256"])

    def test_normalize_company_name(self):
        self.assertEqual(normalize_company_name("三井科技股份有限公司"), "三井科技")
        self.assertEqual(normalize_company_name("富邦媒體科技(momo)股份有限公司"), "富邦媒體科技momo")
        self.assertEqual(normalize_company_name("台灣虎航股份有限公司"), "台灣虎航")

    def test_parse_date_str(self):
        self.assertEqual(parse_date_str("10.09", 2026), date(2026, 10, 9))
        self.assertEqual(parse_date_str("2.29", 2024), date(2024, 2, 29))
        self.assertIsNone(parse_date_str("invalid", 2026))
        self.assertIsNone(parse_date_str(None, 2026))

    def test_save_yes123_batch_to_fake_db(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        jobs = parse_job_cards(soup)
        now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
        batch = {
            "manifest": {
                "batchId": "20261009T120000Z-test",
                "seriesKey": "series12345678901234",
                "snapshotDate": "2026-10-09",
                "snapshotDateTime": now.isoformat(),
                "request": {"category_code": "2_1006_0002_0003"},
                "codeKind": "YES123_WORK_MODE",
                "rows": len(jobs),
            },
            "manifest_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "jobs": jobs,
            "raw_rows": [(1, idx, j) for idx, j in enumerate(jobs)],
        }

        conn = FakeConnection()
        summary = save_yes123_batch(conn, batch, Jsonb=lambda x: x)
        self.assertEqual(summary["status"], "loaded-silver-complete")
        self.assertEqual(summary["jobs"], 2)
        self.assertEqual(summary["companies"], 2)

        # Verify that SQL statements were executed for Bronze and Silver
        executed_sqls = [stmt[0] for stmt in conn.executed]
        self.assertTrue(any("bronze.capture_batches" in s for s in executed_sqls))
        self.assertTrue(any("bronze.raw_job_rows" in s for s in executed_sqls))
        self.assertTrue(any("silver.company_dimension" in s for s in executed_sqls))
        self.assertTrue(any("silver.company_master" in s for s in executed_sqls))
        self.assertTrue(any("silver.area_dimension" in s for s in executed_sqls))
        self.assertTrue(any("silver.job_current" in s for s in executed_sqls))
        self.assertTrue(any("silver.job_snapshots" in s for s in executed_sqls))
        self.assertTrue(any("silver.job_salary_observations" in s for s in executed_sqls))
        self.assertTrue(any("silver.job_category_snapshots" in s for s in executed_sqls))

    def test_publish_yes123_batch(self):
        import tempfile
        from acquisition.platforms.yes123.capture import publish_yes123_batch
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            batch = {
                "series_key": "testseries1234567890",
                "batch_id": "testbatch123",
                "manifest": {"rows": 1},
                "jobs": [],
            }
            fpath = publish_yes123_batch(out_path, batch)
            self.assertTrue(fpath.exists())
            self.assertTrue((out_path / "current.json").exists())

    def test_annealing_pacer_dynamics(self):
        from acquisition.platforms.yes123.annealer import AnnealingPacer

        pacer = AnnealingPacer(min_interval=1.0, max_interval=10.0, initial_interval=2.0, max_retries=3, cooldown_seconds=1.0)
        self.assertEqual(pacer.current_interval, 2.0)
        self.assertFalse(pacer.is_circuit_open)

        # 1. Healthy responses accelerate
        for _ in range(5):
            pacer.on_success(latency=0.5)
        self.assertLess(pacer.current_interval, 2.0)

        # 2. High latency slows down
        pacer.on_success(latency=4.5)
        self.assertGreater(pacer.current_interval, 1.9)

        # 3. Throttle increases interval multiplicatively
        delay = pacer.on_throttle(429, retry_after=0.01)
        self.assertGreaterEqual(delay, 0.01)
        self.assertGreater(pacer.current_interval, 2.5)

        # 4. Consecutive throttles trip circuit breaker
        pacer.on_throttle(503, retry_after=0.01)
        pacer.on_throttle(503, retry_after=0.01)
        self.assertTrue(pacer.is_circuit_open)

    def test_overseas_location_classification(self):
        self.assertTrue(is_taiwan_location("台北市松山區"))
        self.assertTrue(is_taiwan_location("臺北市北投區大業路136號"))
        self.assertTrue(is_taiwan_location("桃園市大溪區"))
        self.assertFalse(is_taiwan_location("美中地區德克薩"))
        self.assertFalse(is_taiwan_location("中美洲墨西哥墨西哥"))
        self.assertFalse(is_taiwan_location("東南亞越南平陽省"))
        self.assertFalse(is_taiwan_location("日本東京都港區"))

    def test_parse_overseas_job_card(self):
        html = """
        <div class="Job_opening_item">
            <div class="Job_opening_item_title">
                <a href="/admin/job.asp?p_id=C003&job_id=J003">墨西哥廠主管</a>
            </div>
            <a href="/admin/comp_info.asp?p_id=C003">國際科技股份有限公司</a>
            <div class="Job_opening_item_title_payment">月薪 80,000元</div>
            <div class="Job_opening_item_date">10.09</div>
            <div class="Job_opening_item_info">
                <span>中美洲墨西哥</span>
                <span>全職</span>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        cards = parse_job_cards(soup)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["raw_area"], "中美洲墨西哥")
        self.assertEqual(cards[0]["standardized_address"], "中美洲墨西哥")
        self.assertTrue(cards[0]["is_overseas"])

    def test_parse_job_detail_dom(self):
        html = """
        <div class="job_explain">
            <ul>
                <li>
                    <span class="left_title">工作地點：</span>
                    <span class="right_main">台北市北投區大業路136號 <a href="https://maps.google.com.tw/maps?q=test">地圖</a></span>
                </li>
                <li>
                    <span class="left_title">電腦技能：</span>
                    <span class="right_main">資料庫：PL/SQL</span>
                </li>
                <li>
                    <span class="left_title">工作技能：</span>
                    <span class="right_main">專案需求分析</span>
                </li>
            </ul>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        detail = parse_job_detail_dom(soup)
        self.assertEqual(detail["job_address"], "台北市北投區大業路136號")
        self.assertFalse(detail["is_overseas"])
        self.assertEqual(detail["google_maps_url"], "https://maps.google.com.tw/maps?q=test")
        self.assertEqual(detail["computer_skills"], ["資料庫：PL/SQL"])
        self.assertEqual(detail["work_skills"], ["專案需求分析"])


if __name__ == "__main__":
    unittest.main()
