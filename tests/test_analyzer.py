import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from src.analyzer import Analyzer
from src.config import ConfigManager

class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.mock_cm = MagicMock(spec=ConfigManager)
        self.mock_api = MagicMock()
        self.mock_rep = MagicMock()
        self.analyzer = Analyzer(self.mock_cm, self.mock_api, self.mock_rep)

    def test_calculate_mbps_interval(self):
        # Case 1: Interval bytes available (delta > 0)
        flow = {
            "dst_dbo": 1000000, "dst_dbi": 1000000, "ddms": 1000
        }
        # (2000000 bytes * 8 bits) / (1 sec) = 16 Mbps
        val, note, _, _ = self.analyzer.calculate_mbps(flow)
        self.assertAlmostEqual(val, 16.0)
        self.assertEqual(note, "(Interval)")

    def test_calculate_mbps_hybrid_fallback(self):
        # Case 2: Interval bytes 0, Fallback to Total
        flow = {
            "dst_dbo": 0, "dst_dbi": 0,
            "dst_tbo": 500000, "dst_tbi": 500000,
            "interval_sec": 1
        }
        # (1000000 bytes * 8) / 1 sec = 8 Mbps
        val, note, _, _ = self.analyzer.calculate_mbps(flow)
        self.assertAlmostEqual(val, 8.0)
        self.assertEqual(note, "(Avg)")

    def test_sliding_window_filter(self):
        # Rule window = 10 mins
        rule = {"type": "traffic", "threshold_window": 10}
        
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        start_limit = datetime(2023, 1, 1, 11, 50, 0, tzinfo=timezone.utc)
        
        # Flow inside window (11:55)
        f_in = {"timestamp": "2023-01-01T11:55:00Z", "policy_decision": "blocked"}
        self.assertTrue(self.analyzer.check_flow_match(rule, f_in, start_limit))
        
        # Flow outside window (11:45)
        f_out = {"timestamp": "2023-01-01T11:45:00Z", "policy_decision": "blocked"}
        self.assertFalse(self.analyzer.check_flow_match(rule, f_out, start_limit))

if __name__ == '__main__':
    unittest.main()
