import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
import cache_sync
import mirror
import test_mirror

class CacheSyncTests(unittest.TestCase):
    def setUp(self):
        fixture = test_mirror.MirrorTests()
        fixture.setUp()
        self.now, self.data = fixture.now, fixture.data
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "cache").mkdir()

    def put(self, data=None):
        (self.root / "cache" / "zarjpy-analysis.json").write_text(
            json.dumps(data or self.data), encoding="utf-8")

    def test_missing_cache_never_uses_network_or_token(self):
        with patch("mirror.api") as api, patch("mirror.publish") as publish:
            result = cache_sync.sync_once(self.root, None, self.now)
        self.assertEqual(result["stage"], "awaiting_local_source")
        api.assert_not_called()
        publish.assert_not_called()

    def test_old_cache_never_fetches_replacement(self):
        self.put()
        with patch("mirror.api") as api, patch("mirror.publish") as publish:
            with self.assertRaises(ValueError):
                cache_sync.sync_once(self.root, "dummy", self.now + timedelta(seconds=301))
        api.assert_not_called()
        publish.assert_not_called()

    def test_publish_once_and_local_dedup(self):
        self.put()
        result = mirror.build(self.data, self.now)
        remote = {"sha": "abc", "content": base64.b64encode(json.dumps(result).encode()).decode()}
        with patch("mirror.publish") as publish, patch("mirror.api", return_value=remote) as api, patch("mirror.datetime", wraps=datetime) as clock:
            clock.now.return_value = self.now
            first = cache_sync.sync_once(self.root, "dummy", self.now)
            second = cache_sync.sync_once(self.root, "dummy", self.now)
        self.assertEqual(first["stage"], "complete")
        self.assertEqual(second["stage"], "unchanged")
        self.assertEqual(publish.call_count, 1)
        self.assertEqual(api.call_count, 1)
        original = json.loads((self.root / "cache" / "zarjpy-analysis.json").read_text())
        self.assertEqual(original, self.data)

    def test_remote_failure_does_not_checkpoint(self):
        self.put()
        with patch("mirror.publish", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                cache_sync.sync_once(self.root, "dummy", self.now)
        self.assertFalse((self.root / "published.json").exists())

    def test_secret_local_source_not_published(self):
        data = copy.deepcopy(self.data)
        data["api_key"] = "not-a-real-key"
        self.put(data)
        with patch("mirror.publish") as publish:
            with self.assertRaises(ValueError):
                cache_sync.sync_once(self.root, "dummy", self.now)
        publish.assert_not_called()
