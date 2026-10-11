"""Unit tests for category crosswalk coverage audit."""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.platforms.yes123.crosswalk_audit import fetch_crosswalk_audit


class CrosswalkAuditTests(unittest.TestCase):
    def test_fetch_crosswalk_audit_structure(self):
        mock_conn = MagicMock()
        status_rows = [
            ("yes123", "CONFIRMED", 574, 1.0, 1.0, 1.0)
        ]
        canonical_rows = [
            (2007000000, "資訊軟體系統類", 31)
        ]
        collision_rows = []
        anomalies_rows = []
        job_coverage_row = (39392, 39392, 0)

        def execute_side_effect(query, params=None):
            m = MagicMock()
            q = query.strip()
            if "GROUP BY source_platform, mapping_status" in q:
                m.fetchall.return_value = status_rows
            elif "GROUP BY c.canonical_job_cat_code" in q:
                m.fetchall.return_value = canonical_rows
            elif "NOT LIKE '2!_%' ESCAPE '!'" in q:
                m.fetchall.return_value = collision_rows
            elif "mapping_status != 'CONFIRMED' AND canonical_job_cat_code IS NOT NULL" in q:
                m.fetchall.return_value = anomalies_rows
            elif "COUNT(DISTINCT job_no)" in q:
                m.fetchone.return_value = job_coverage_row
            else:
                m.fetchall.return_value = []
                m.fetchone.return_value = None
            return m

        mock_conn.execute.side_effect = execute_side_effect

        mock_conn.__enter__.return_value = mock_conn
        from unittest.mock import patch
        with patch("psycopg.connect", return_value=mock_conn):
            result = fetch_crosswalk_audit({})

        self.assertEqual(result["totalCrosswalkCodes"], 574)
        self.assertEqual(len(result["statusSummary"]), 1)
        self.assertEqual(result["wildcardCollisions"], [])
        self.assertEqual(result["inconsistentRows"], [])
        self.assertEqual(result["observedJobCoverage"]["totalYes123Jobs"], 39392)


if __name__ == "__main__":
    unittest.main()
