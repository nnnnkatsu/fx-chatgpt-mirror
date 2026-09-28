import base64
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import mirror
import observed_sync
import test_mirror

class ObservedTests(unittest.TestCase):
    def setUp(self):
        f=test_mirror.MirrorTests(); f.setUp(); self.now,self.data=f.now,f.data
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); (self.root/'cache').mkdir()
    def put(self,data):
        (self.root/'cache'/'zarjpy-analysis.json').write_text(json.dumps(data))
    def test_stale_cache_identified_without_network(self):
        self.put(self.data)
        with patch('mirror.api') as api,patch('mirror.publish') as publish:
            s=observed_sync.observed_sync(self.root,None,'ZARJPY',self.now+timedelta(hours=3))
        self.assertEqual(s['stage'],'awaiting_fresh_source')
        self.assertEqual(s['local_fetched_at_utc'],'2026-09-25T12:00:00.000Z')
        self.assertEqual(s['local_cache_age_seconds'],10800)
        self.assertEqual(s['github_requests'],0)
        self.assertEqual(s['consecutive_source_waits'],1)
        self.assertEqual(s['consecutive_failures'],0)
        api.assert_not_called(); publish.assert_not_called()
    def test_failure_then_three_distinct_updates(self):
        self.put(self.data)
        with patch('mirror.publish',side_effect=RuntimeError('GitHub HTTP 403')):
            failure=observed_sync.observed_sync(self.root,'dummy','ZARJPY',self.now)
        self.assertEqual(failure['consecutive_failures'],1)
        for step in range(3):
            now=self.now+timedelta(seconds=120*step)
            data=copy.deepcopy(self.data); data['fetched_at_utc']=mirror.stamp(now)
            for tf,part in data['analysis'].items():
                part['candle_age_seconds']=(now-mirror.utc(part['latest_candle_at_utc'],tf=='1day')).total_seconds()
            self.put(data); payload=mirror.build(data,now)
            remote={'sha':'a'*40,'content':base64.b64encode(json.dumps(payload).encode()).decode()}
            with patch('mirror.publish'),patch('mirror.api',return_value=remote),patch('mirror.datetime',wraps=datetime) as clock:
                clock.now.return_value=now
                s=observed_sync.observed_sync(self.root,'dummy','ZARJPY',now)
            self.assertEqual(s['stage'],'complete'); self.assertEqual(s['consecutive_failures'],0)
            self.assertEqual(s['fetched_at_utc'],data['fetched_at_utc'])
    def test_unknown_errors_do_not_leak_text(self):
        self.put(self.data)
        with patch('mirror.publish',side_effect=RuntimeError('Bearer PRIVATE_EXAMPLE')):
            s=observed_sync.observed_sync(self.root,'dummy','ZARJPY',self.now)
        text=(self.root/'mirror-events.jsonl').read_text()
        self.assertNotIn('PRIVATE_EXAMPLE',text)
        self.assertEqual(s['reason'],'validation_or_io_failure')
    def test_audit_logs_http_code_and_commit_only(self):
        self.put(self.data)
        def fail(payload,token,pair,audit):
            audit({'method':'PUT','http_code':403,'body':'PRIVATE_EXAMPLE'})
            raise RuntimeError('GitHub HTTP 403')
        with patch('mirror.publish',side_effect=fail):
            s=observed_sync.observed_sync(self.root,'dummy','ZARJPY',self.now)
        self.assertTrue(s['update_attempted']); self.assertEqual(s['github_http_code'],403)
        self.assertNotIn('PRIVATE_EXAMPLE',json.dumps(s))
