"""Shared conservative credit admission. No HTTP and no credentials.

Every upstream caller must use the SAME database and this gate BEFORE dispatch.
Uncertain requests remain charged. Defaults refuse active collection.
"""
import sqlite3
import time
import uuid

PAIRS = {"ZARJPY", "USDJPY", "MXNJPY", "GBPUSD"}

class Gate:
    def __init__(self, database, policy):
        self.policy = policy
        self.db = sqlite3.connect(str(database), timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, pair TEXT, kind TEXT, at REAL, cost INTEGER, finished INTEGER DEFAULT 0)")
        self.db.execute("CREATE INDEX IF NOT EXISTS attempts_time ON attempts(at)")
    def close(self):
        self.db.close()
    def admit(self, pair, kind, now=None):
        now = time.time() if now is None else now
        p = self.policy
        if pair not in PAIRS or kind not in ("scheduled", "manual", "retry"):
            return {"allowed": False, "reason": "invalid_request"}
        if not p.get("enabled") or not p.get("all_upstream_callers_gated"):
            return {"allowed": False, "reason": "collection_disabled"}
        if pair not in p.get("active_pairs", []):
            return {"allowed": False, "reason": "pair_not_enabled"}
        fields = ("credits_per_60s", "credits_per_24h", "credits_per_31days",
                  "manual_reserve_per_24h", "retry_reserve_per_24h")
        if any(type(p.get(k)) is not int or p[k] < 0 for k in fields):
            return {"allowed": False, "reason": "budget_unconfigured"}
        cost = p.get("analysis_cost_upper_bound", {}).get(pair)
        if type(cost) is not int or cost <= 0:
            return {"allowed": False, "reason": "cost_unknown"}
        cooldown = p.get("pair_cooldown_seconds", 120)
        lease = p.get("inflight_timeout_seconds", 180)
        if type(cooldown) is not int or cooldown < 120 or type(lease) is not int or lease < 90:
            return {"allowed": False, "reason": "invalid_policy"}
        self.db.execute("BEGIN IMMEDIATE")
        try:
            # Caller transport MUST stop before this lease expires.
            active = self.db.execute("SELECT pair, at FROM attempts WHERE finished=0 AND at>? ORDER BY at DESC LIMIT 1", (now-lease,)).fetchone()
            if active:
                return {"allowed": False, "reason": "refresh_in_progress", "pair": active[0]}
            last = self.db.execute("SELECT MAX(at) FROM attempts WHERE pair=?", (pair,)).fetchone()[0]
            if last is not None and now-last < cooldown:
                return {"allowed": False, "reason": "pair_cooldown", "retry_after": cooldown-(now-last)}
            for seconds, field in ((60, "credits_per_60s"), (86400, "credits_per_24h"), (2678400, "credits_per_31days")):
                used = self.db.execute("SELECT COALESCE(SUM(cost),0) FROM attempts WHERE at>?", (now-seconds,)).fetchone()[0]
                if used+cost > p[field]:
                    return {"allowed": False, "reason": field}
            # Scheduled work cannot eat the explicitly reserved manual/retry pool.
            if kind == "scheduled":
                used = self.db.execute("SELECT COALESCE(SUM(cost),0) FROM attempts WHERE at>? AND kind='scheduled'", (now-86400,)).fetchone()[0]
                available = p["credits_per_24h"]-p["manual_reserve_per_24h"]-p["retry_reserve_per_24h"]
                if used+cost > available:
                    return {"allowed": False, "reason": "manual_and_retry_reserve"}
            elif kind == "manual":
                used = self.db.execute("SELECT COALESCE(SUM(cost),0) FROM attempts WHERE at>? AND kind!='retry'", (now-86400,)).fetchone()[0]
                if used+cost > p["credits_per_24h"]-p["retry_reserve_per_24h"]:
                    return {"allowed": False, "reason": "retry_reserve"}
            ident = uuid.uuid4().hex
            self.db.execute("INSERT INTO attempts(id,pair,kind,at,cost) VALUES(?,?,?,?,?)", (ident,pair,kind,now,cost))
            return {"allowed": True, "reservation": ident, "reserved_credits": cost}
        finally:
            self.db.execute("COMMIT")
    def finish(self, reservation):
        # No refund: an HTTP error or timeout may already have consumed credits.
        self.db.execute("UPDATE attempts SET finished=1 WHERE id=?", (reservation,))

def schedule_due(detection_at, now):
    """One prefetch window only: T-120 through T. Caller persists event IDs."""
    return detection_at - 120 <= now <= detection_at
