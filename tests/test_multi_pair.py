import base64
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import mirror
import cache_sync
import test_mirror

class MultiPairTests(unittest.TestCase):
    def setUp(self):
        f = test_mirror.MirrorTests(); f.setUp()
        self.data, self.now = f.data, f.now

    def test_each_pair_preserves_source_and_rejects_cross_pair(self):
        for pair, symbol in mirror.PAIRS.items():
            data = copy.deepcopy(self.data); data['symbol'] = symbol
            payload = mirror.build(data, self.now, pair)
            self.assertEqual({k: payload[k] for k in data}, data)
            for other in mirror.PAIRS:
                if pair != other:
                    with self.assertRaises(ValueError): mirror.validate(data, self.now, other)

    def test_api_targets_correct_file(self):
        for pair in mirror.PAIRS:
            with patch('mirror.urlopen') as open_url:
                open_url.return_value.__enter__.return_value.read.return_value = '{}'
                mirror.api('GET', 'dummy', pair=pair)
                self.assertTrue(open_url.call_args.args[0].full_url.endswith('/data/' + pair.lower() + '.json?ref=main'))

    def test_checkpoints_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'cache').mkdir()
            for pair, symbol in mirror.PAIRS.items():
                data = copy.deepcopy(self.data); data['symbol'] = symbol
                (root/'cache'/(pair.lower()+'-analysis.json')).write_text(json.dumps(data))
                payload = mirror.build(data, self.now, pair)
                remote = {'sha': pair, 'content': base64.b64encode(json.dumps(payload).encode()).decode()}
                with patch('mirror.datetime', wraps=datetime) as clock, patch('mirror.publish') as publish, patch('mirror.api', return_value=remote):
                    clock.now.return_value = self.now
                    self.assertEqual(cache_sync.sync_once(root,'dummy',self.now,pair)['stage'], 'complete')
                    self.assertEqual(cache_sync.sync_once(root,'dummy',self.now,pair)['stage'], 'unchanged')
                    self.assertEqual(publish.call_count, 1)
                    self.assertEqual(publish.call_args.kwargs['pair'], pair)
            self.assertEqual(len(list(root.glob('published*.json'))), 3)
