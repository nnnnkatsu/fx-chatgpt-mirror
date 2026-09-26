import copy
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from quota_gate import Gate, schedule_due

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"budget.sqlite"
        self.policy = dict(enabled=True, all_upstream_callers_gated=True,
            active_pairs=["ZARJPY","USDJPY","MXNJPY","GBPUSD"],
            credits_per_60s=8, credits_per_24h=24, credits_per_31days=100,
            manual_reserve_per_24h=8, retry_reserve_per_24h=4,
            analysis_cost_upper_bound={p:4 for p in ("ZARJPY","USDJPY","MXNJPY","GBPUSD")},
            pair_cooldown_seconds=120,inflight_timeout_seconds=180)
        self.gate = Gate(self.path,self.policy)
        self.addCleanup(self.gate.close)
    def test_disabled_without_global_coverage(self):
        self.policy["all_upstream_callers_gated"]=False
        self.assertEqual(self.gate.admit("ZARJPY","manual",100)["reason"],"collection_disabled")
    def test_unknown_cost_is_not_assumed_to_be_one(self):
        self.policy["analysis_cost_upper_bound"]["ZARJPY"]=None
        self.assertEqual(self.gate.admit("ZARJPY","manual",100)["reason"],"cost_unknown")
    def test_all_pairs_share_minute_budget(self):
        for pair,t in (("ZARJPY",100),("USDJPY",101)):
            r=self.gate.admit(pair,"manual",t); self.assertTrue(r["allowed"]); self.gate.finish(r["reservation"])
        self.assertEqual(self.gate.admit("MXNJPY","manual",102)["reason"],"credits_per_60s")
    def test_failure_not_refunded(self):
        self.policy["credits_per_60s"]=4
        r=self.gate.admit("ZARJPY","manual",100)
        self.gate.finish(r["reservation"])
        self.assertFalse(self.gate.admit("USDJPY","manual",101)["allowed"])
    def test_manual_reserve_survives_scheduled_work(self):
        for t in (100,300,500):
            r=self.gate.admit("ZARJPY","scheduled",t); self.assertTrue(r["allowed"]); self.gate.finish(r["reservation"])
        self.assertEqual(self.gate.admit("ZARJPY","scheduled",700)["reason"],"manual_and_retry_reserve")
        self.assertTrue(self.gate.admit("USDJPY","manual",701)["allowed"])
    def test_manual_does_not_bypass_cooldown(self):
        r=self.gate.admit("ZARJPY","scheduled",100); self.gate.finish(r["reservation"])
        self.assertEqual(self.gate.admit("ZARJPY","manual",101)["reason"],"pair_cooldown")
    def test_inflight_coalesces_requests(self):
        self.gate.admit("ZARJPY","scheduled",100)
        self.assertEqual(self.gate.admit("ZARJPY","manual",101)["reason"],"refresh_in_progress")
        self.assertEqual(self.gate.admit("USDJPY","manual",101)["reason"],"refresh_in_progress")
    def test_concurrent_admissions_do_not_double_spend(self):
        def call(pair):
            g=Gate(self.path,self.policy)
            try: return g.admit(pair,"manual",100)
            finally: g.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            answers=list(pool.map(call,("ZARJPY","USDJPY","MXNJPY","GBPUSD")))
        self.assertEqual(sum(r["allowed"] for r in answers),1)
    def test_no_post_detection_polling_window(self):
        self.assertTrue(schedule_due(1000,880))
        self.assertFalse(schedule_due(1000,1001))
