import base64
import copy
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from urllib.error import HTTPError
import mirror

class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
        self.data = {"ok": True, "type": "analysis", "symbol": "ZAR/JPY", "source": "Twelve Data",
                     "price": 9.6, "fetched_at_utc": "2026-09-25T12:00:00Z", "analysis": {}}
        for tf, interval in mirror.INTERVALS.items():
            date = "2026-09-25Z" if tf == "1day" else "2026-09-25T12:00:00Z"
            self.data["analysis"][tf] = {"timezone": "UTC", "latest_candle_at_utc": date,
                "candle_age_seconds": 43200 if tf == "1day" else 0,
                "current_candle": {"datetime_utc": date}, "candles": [{"close": 9.6}],
                "indicators": {"rsi14": 50}}
    def test_preserves_every_original_field(self):
        original = copy.deepcopy(self.data)
        result = mirror.build(self.data, self.now)
        self.assertEqual(self.data, original)
        self.assertEqual({k: result[k] for k in original}, original)
        self.assertIsNone(result["generated_at_utc"])
        self.assertEqual(result["source"], "Twelve Data")
        self.assertEqual(result["analysis"]["1day"]["latest_candle_at_utc"], "2026-09-25Z")
    def test_preserves_existing_generation_time(self):
        self.data["generated_at_utc"] = "2026-09-25T12:00:00Z"
        self.assertEqual(mirror.build(self.data, self.now)["generated_at_utc"], self.data["generated_at_utc"])
    def test_source_error(self):
        self.data["ok"] = False
        with self.assertRaises(ValueError): mirror.build(self.data, self.now)
    def test_wrong_symbol(self):
        self.data["symbol"] = "USD/JPY"
        with self.assertRaises(ValueError): mirror.build(self.data, self.now)
    def test_stale_fetch(self):
        with self.assertRaises(ValueError): mirror.validate(self.data, self.now + timedelta(seconds=301))
    def test_future_fetch(self):
        with self.assertRaises(ValueError): mirror.validate(self.data, self.now - timedelta(seconds=1))
    def test_stale_candle_even_with_new_fetch(self):
        part = self.data["analysis"]["1min"]
        part["latest_candle_at_utc"] = part["current_candle"]["datetime_utc"] = "2026-09-25T11:00:00Z"
        part["candle_age_seconds"] = 3600
        with self.assertRaises(ValueError): mirror.validate(self.data, self.now)
    def test_missing_timeframe(self):
        del self.data["analysis"]["4h"]
        with self.assertRaises(KeyError): mirror.validate(self.data, self.now)
    def test_inconsistent_age(self):
        self.data["analysis"]["1h"]["candle_age_seconds"] = 1000
        with self.assertRaises(ValueError): mirror.validate(self.data, self.now)
    def test_secret_field(self):
        self.data["api_key"] = "fake"
        with self.assertRaises(ValueError): mirror.build(self.data, self.now)
    def test_secret_url(self):
        self.data["debug"] = "https://example.test/?apikey=fake"
        with self.assertRaises(ValueError): mirror.build(self.data, self.now)
    def test_nonfinite_price(self):
        self.data["price"] = float("nan")
        with self.assertRaises(ValueError): mirror.build(self.data, self.now)
    def test_timezone_required(self):
        with self.assertRaises(ValueError): mirror.utc("2026-09-25T12:00:00")
    def test_identical_snapshot_no_put(self):
        payload = mirror.build(self.data, self.now)
        current = {"content": base64.b64encode(json.dumps(payload).encode()).decode(), "sha": "old"}
        with patch("mirror.datetime", wraps=datetime) as clock, patch("mirror.api", return_value=current) as api:
            clock.now.return_value = self.now
            mirror.publish(payload, "dummy")
            self.assertEqual(api.call_count, 1)
    def test_conflict_rereads_sha(self):
        payload = mirror.build(self.data, self.now)
        empty = {"content": base64.b64encode(b"{}").decode(), "sha": "old"}
        updated = dict(empty, sha="new")
        error = HTTPError(mirror.API, 409, "conflict", {}, None)
        with patch("mirror.datetime", wraps=datetime) as clock, patch("mirror.api", side_effect=[empty,error,updated,{}]) as api, patch("mirror.time.sleep"):
            clock.now.return_value = self.now
            mirror.publish(payload, "dummy")
            self.assertEqual(api.call_args_list[-1].args[2]["sha"], "new")
    def test_forbidden_not_retried(self):
        payload = mirror.build(self.data, self.now)
        with patch("mirror.datetime", wraps=datetime) as clock, patch("mirror.api", side_effect=HTTPError(mirror.API,403,"forbidden",{},None)) as api:
            clock.now.return_value = self.now
            with self.assertRaises(RuntimeError): mirror.publish(payload, "dummy")
            self.assertEqual(api.call_count, 1)

if __name__ == "__main__":
    unittest.main()
