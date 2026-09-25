import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import mirror

class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
        self.analysis = {"pair": "ZARJPY", "nested": {"candles": [1, 2, 3]}, "value": 9.1}
        self.meta = {"source": mirror.SOURCE, "pair": "ZARJPY", "public_export_reviewed": True,
            "generated_at_utc": "2026-09-25T12:00:00Z", "fetched_at_utc": "2026-09-25T12:00:00Z",
            "candles": {tf: {"latest_candle_at_utc": "2026-09-25T" + ("00" if tf == "1day" else "12") + ":00:00Z",
                "timestamp_semantics": "open", "is_closed": False} for tf in ("1min", "1h", "4h", "1day")}}
    def test_preserves_analysis(self):
        original = copy.deepcopy(self.analysis)
        result = mirror.build(self.analysis, self.meta, self.now)
        self.assertEqual(result["analysis"], original)
        self.assertFalse(result["tradable"])
        self.assertEqual(result["candle_age_seconds"], 0)
    def test_rejects_stale_fetch(self):
        self.meta["fetched_at_utc"] = "2026-09-25T11:54:59Z"
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_rejects_future(self):
        self.meta["generated_at_utc"] = "2026-09-25T12:00:01Z"
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_rejects_stale_candle_with_fresh_fetch(self):
        self.meta["candles"]["1h"]["latest_candle_at_utc"] = "2026-09-25T10:00:00Z"
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_rejects_secret(self):
        self.analysis["nested"]["api_key"] = "dummy-not-a-real-key"
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_rejects_missing_period(self):
        del self.meta["candles"]["1min"]
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_rejects_unreviewed(self):
        self.meta["public_export_reviewed"] = False
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_rejects_false_closed_claim(self):
        self.meta["candles"]["1h"]["is_closed"] = True
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_no_timezone_guess(self):
        self.meta["fetched_at_utc"] = "2026-09-25T12:00:00"
        with self.assertRaises(ValueError): mirror.build(self.analysis, self.meta, self.now)
    def test_skip_existing_same_export(self):
        payload = mirror.build(self.analysis, self.meta, self.now)
        current = {"content": mirror.base64.b64encode(mirror.json.dumps(payload).encode()).decode(), "sha": "example"}
        with patch("mirror.datetime", wraps=datetime) as clock, patch("mirror.api", return_value=current) as api:
            clock.now.return_value = self.now
            mirror.publish(payload, "dummy-test-value")
            self.assertEqual(api.call_count, 1)

if __name__ == "__main__":
    unittest.main()
