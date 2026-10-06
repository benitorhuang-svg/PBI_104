from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.salary_parser import extract_salary_observations


class SalaryParserTests(unittest.TestCase):
    def description(self, text):
        return extract_salary_observations("40000", "50000", text)[1:]

    def test_explicit_monthly_lower_bound_keeps_open_maximum(self):
        text = "月薪四萬以上"
        row = self.description(text)[0]
        self.assertEqual(row["amount_min"], Decimal(40000))
        self.assertIsNone(row["amount_max"])
        self.assertEqual(row["range_kind"], "MIN_ONLY")
        self.assertEqual(row["pay_period"], "MONTH")
        self.assertEqual(row["currency_code"], "TWD")
        self.assertEqual(row["currency_basis"], "PLATFORM_DEFAULT")
        self.assertEqual(row["parse_status"], "PARSED")
        self.assertIn("CURRENCY_DEFAULTED", row["quality_flags"])
        self.assertEqual(row["evidence_text"], "月薪四萬以上")
        self.assertEqual(text[row["evidence_start"]:row["evidence_end"]], row["evidence_text"])

    def test_bare_four_wan_above_does_not_infer_month(self):
        row = self.description("四萬以上")[0]
        self.assertEqual(row["amount_min"], Decimal(40000))
        self.assertEqual(row["pay_period"], "UNKNOWN")
        self.assertEqual(row["currency_code"], "TWD")
        self.assertEqual(row["currency_basis"], "PLATFORM_DEFAULT")
        self.assertIn("PAY_PERIOD_UNKNOWN", row["quality_flags"])
        self.assertEqual(row["parse_status"], "NEEDS_REVIEW")

    def test_hourly_and_annual_range_with_explicit_currency(self):
        hourly = self.description("每小時200元")[0]
        self.assertEqual(hourly["pay_period"], "HOUR")
        self.assertEqual(hourly["currency_code"], "TWD")
        self.assertEqual(hourly["amount_min"], Decimal(200))
        self.assertIsNone(hourly["amount_max"])
        self.assertEqual(hourly["range_kind"], "MIN_ONLY")
        annual = self.description("年薪60萬～80萬元")[0]
        self.assertEqual(annual["pay_period"], "YEAR")
        self.assertEqual(annual["range_kind"], "RANGE")
        self.assertEqual(annual["amount_min"], Decimal(600000))
        self.assertEqual(annual["amount_max"], Decimal(800000))
        self.assertEqual(annual["currency_code"], "TWD")

    def test_hour_shorthand_and_bare_range_use_lower_and_upper_bounds(self):
        hourly = self.description("150/hr")[0]
        self.assertEqual(hourly["amount_min"], Decimal(150))
        self.assertIsNone(hourly["amount_max"])
        self.assertEqual(hourly["pay_period"], "HOUR")
        self.assertEqual(hourly["currency_basis"], "PLATFORM_DEFAULT")
        salary_range = self.description("35000~42000")[0]
        self.assertEqual(salary_range["amount_min"], Decimal(35000))
        self.assertEqual(salary_range["amount_max"], Decimal(42000))
        self.assertEqual(salary_range["range_kind"], "RANGE")
        self.assertEqual(salary_range["pay_period"], "UNKNOWN")

    def test_upper_bound_and_variable_bonus_remain_separate(self):
        upper = self.description("月薪最高五萬元")[0]
        self.assertIsNone(upper["amount_min"])
        self.assertEqual(upper["amount_max"], Decimal(50000))
        self.assertEqual(upper["range_kind"], "MAX_ONLY")
        annual = self.description("年薪60萬至80萬元，另有年終獎金")
        self.assertEqual(len(annual), 1)
        self.assertEqual(annual[0]["compensation_component"], "BASE")

    def test_explicit_currency_and_range_are_preserved(self):
        row = self.description("月薪 NT$40,000 至 NT$50,000")[0]
        self.assertEqual(row["amount_min"], Decimal(40000))
        self.assertEqual(row["amount_max"], Decimal(50000))
        self.assertEqual(row["pay_period"], "MONTH")
        self.assertEqual(row["currency_basis"], "EXPLICIT_TEXT")
        self.assertEqual(row["parse_status"], "PARSED")
        conflict = self.description("月薪 USD 40000元")[0]
        self.assertIsNone(conflict["currency_code"])
        self.assertEqual(conflict["parse_status"], "NEEDS_REVIEW")
        self.assertIn("CURRENCY_CONFLICT", conflict["quality_flags"])

    def test_disclosure_statuses_and_chinese_number(self):
        self.assertEqual(self.description("薪資面議")[0]["parse_status"], "NEGOTIABLE")
        self.assertEqual(self.description("薪資依公司規定")[0]["parse_status"], "NOT_DISCLOSED")
        self.assertEqual(self.description("底薪四萬五千元/月")[0]["amount_min"], Decimal(45000))

    def test_api_values_are_retained_but_not_normalized(self):
        api = extract_salary_observations("0", "9999999", None)[0]
        self.assertEqual(api["parse_status"], "SENTINEL_CANDIDATE")
        self.assertEqual(api["raw_value_min"], "0")
        self.assertEqual(api["raw_value_max"], "9999999")
        self.assertIsNone(api["amount_min"])
        self.assertEqual(api["pay_period"], "UNKNOWN")
        self.assertEqual(api["currency_code"], "TWD")
        self.assertEqual(api["currency_basis"], "PLATFORM_DEFAULT")
        normal = extract_salary_observations("40000", "50000", None)[0]
        self.assertEqual(normal["parse_status"], "API_UNIT_UNMAPPED")
        self.assertIsNone(normal["amount_max"])


if __name__ == "__main__":
    unittest.main()
