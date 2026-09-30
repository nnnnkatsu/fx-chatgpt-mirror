import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sakura_runner

class EventCredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_event_never_uses_or_persists_request_environment(self):
        with patch.dict(os.environ, {"FX_MIRROR_GITHUB_TOKEN": "request-value"}):
            self.assertIsNone(sakura_runner.credential(self.root, event=True))
        self.assertFalse((self.root / "github-credential.json").exists())

    def test_cron_provisions_then_event_reads_same_private_credential(self):
        with patch.dict(os.environ, {"FX_MIRROR_GITHUB_TOKEN": "test-only"}):
            self.assertEqual(sakura_runner.credential(self.root), "test-only")
        with patch.dict(os.environ, {"FX_MIRROR_GITHUB_TOKEN": "ignored"}):
            self.assertEqual(sakura_runner.credential(self.root, event=True), "test-only")
        if os.name != "nt":
            self.assertEqual((self.root / "github-credential.json").stat().st_mode & 0o777, 0o600)

    def test_invalid_event_pair_rejected_before_runtime_or_network(self):
        with self.assertRaises(ValueError):
            sakura_runner.run("GBPUSD")

    @unittest.skipIf(os.name == "nt", "Unix permission check")
    def test_world_readable_credential_refused(self):
        p = self.root / "github-credential.json"
        p.write_text(json.dumps({"token":"test-only"}))
        p.chmod(0o644)
        with self.assertRaises(ValueError):
            sakura_runner.credential(self.root, event=True)
