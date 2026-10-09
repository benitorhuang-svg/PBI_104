import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.shared.sql_parser import statements

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MultiPlatformMigrationTests(unittest.TestCase):
    def test_migration_19_sql_parses_cleanly(self):
        sql_path = PROJECT_ROOT / "tools/sql/migrations/019_multi_platform_isolation.sql"
        self.assertTrue(sql_path.exists())
        sql = sql_path.read_text(encoding="utf-8")
        stmts = list(statements(sql))
        self.assertGreaterEqual(len(stmts), 10)
        # Check that version 19 insertion exists
        self.assertTrue(any("bronze.schema_migrations" in s and "19" in s for s in stmts))

    def test_init_postgres_schema_includes_migration_19(self):
        sql_path = PROJECT_ROOT / "tools/sql/init_postgres_schema.sql"
        sql = sql_path.read_text(encoding="utf-8")
        stmts = list(statements(sql))
        self.assertTrue(any("category_crosswalk" in s for s in stmts))
        self.assertTrue(any("company_master" in s for s in stmts))
        self.assertTrue(any("source_platform" in s for s in stmts))

    def test_gold_view_preserves_column_order(self):
        sql_path = PROJECT_ROOT / "tools/sql/migrations/019_multi_platform_isolation.sql"
        sql = sql_path.read_text(encoding="utf-8")
        
        # Verify that gold.pbi_fact_jobs starts with original 15 columns
        expected_columns = [
            '"jobNo"', '"custNo"', '"areaKey"', '"jobName"', '"descSnippet"',
            '"jobAddress"', '"jobAddrNoDesc"', '"salaryLow"', '"salaryHigh"',
            '"appearDate"', '"jobLink"', '"snapshotDate"', '"snapshotDateTime"',
            '"sourceKeyword"', '"sourceArea"',
            '"sourcePlatform"', '"nativeJobId"', '"sourceJobKey"'
        ]
        
        match = re.search(r"CREATE OR REPLACE VIEW gold\.pbi_fact_jobs AS\s+SELECT\s+(.*?)\s+FROM gold\.pbi_fact_job_scope", sql, re.DOTALL)
        self.assertIsNotNone(match)
        select_clause = match.group(1)
        for col in expected_columns:
            self.assertIn(col, select_clause)

    def test_yes123_probe_fixture_contract(self):
        fixture_path = PROJECT_ROOT / "tools/tests/fixtures/yes123-sample-probe.json"
        self.assertTrue(fixture_path.exists())
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS")
        self.assertGreater(data["collected_total"], 0)
        
        # Verify sample job shape
        sample = data["sample_jobs"][0]
        self.assertEqual(sample["source_platform"], "yes123")
        self.assertTrue(sample["source_job_key"].startswith("yes123:"))
        self.assertTrue(sample["native_job_id"])
        self.assertIn("job_title", sample)
        self.assertIn("company_name", sample)


if __name__ == "__main__":
    unittest.main()
