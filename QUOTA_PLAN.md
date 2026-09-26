# Collection and mirror separation

## Current implementation vs deployment

- Passive runner and capture sidecar were installed on 2026-09-26. The old extra
  polling was stopped. See DEPLOYMENT.md for hashes, backup and server evidence.
- Existing successful ZARJPY analysis responses are copied to a private file;
  the two-minute cron reads only that file. It never requests market data.
- No real fresh source capture or two successful automatic uploads have yet been
  accepted. Isolated PHP tests do not substitute for production acceptance.
- quota_gate.py remains an offline-tested component, NOT a deployed global limit.
  It must cover all upstream callers sharing the Twelve Data key, including
  direct Worker, price and interval routes. A Sakura-only gate is insufficient.
- Scheduled prefetch and authenticated manual refresh remain disabled pending
  timetable, plan allowance, cost and complete caller coverage.

## Intended timings

Scheduled analysis: one preparation at T minus 120 seconds, never a repeating
T +/- 5 minute polling window. Persist the event ID so restarts do not reissue it.
No catch-up burst for missed events after downtime. Schedule timestamps and
timezone must come from the actual existing detection timetable.

Manual analysis: use a validated cache first (up to 300 seconds for higher
timeframes, 60 seconds target for precise entry). If cache is insufficient,
request the SAME admission gate; no force bypass. Same-pair cooldown is at least
120 seconds, and concurrent requests share one in-flight refresh. A 60-second
target is not a guarantee: cooldown/budget can make the caller wait.

The public GitHub RAW URL is READ ONLY. Reading it never triggers collection.
No public GET URL will launch a refresh. An authenticated trigger channel and its
actual ChatGPT availability still need to be selected and verified.
No Twelve Data or GitHub token belongs in a URL or a public JSON.

## Credit budget

Do not count one analysis request as one credit. Measure/inspect the current
Worker's six-timeframe collection, cache behavior and retry fan-out first.
analysis_cost_upper_bound must cover the maximum possible credits for one
admitted operation; every separate retry needs a separate reservation.

The example policy deliberately has null budgets, empty timetable, enabled=false
and all_upstream_callers_gated=false. It refuses active collection. Only ZARJPY is
eligible for the prototype; other pair names exist for shared-budget tests, not
production enablement.

The gate stores attempts in one PRIVATE SQLite database, serializes reservations,
and charges uncertain/failed requests conservatively without refunds. It checks:
- rolling 60-second credits across all currencies;
- rolling 24-hour and rolling 31-day allowances (conservative windows, not assumed
  provider reset times);
- daily allowance reserved for manual requests and retries;
- pair cooldown and a global in-flight lease.

The adapter must terminate requests before the 180-second lease expires (the
current mirror has a 90-second deadline). Expired leases do not refund credits.
Seed recent external usage conservatively before enabling a new ledger. All
pre-existing requests must pass the gate or be included in a conservative budget
allocation; otherwise all_upstream_callers_gated MUST stay false.
Market-closure rules and at most one retry belong in the caller/scheduler and
are NOT implemented by the admission library itself.

## Activation checklist

1. DONE: old polling stopped; passive cron saved.
2. Review live Sakura and Worker collection code without exposing secrets.
3. INSTALLED: passive runner and capture hook; PHP checks pass and original bytes are preserved apart from the hook. Real-response acceptance pending.
4. Verify missing/stale cache causes zero upstream HTTP calls.
5. Confirm plan limits, measured cost and current usage, detection times/timezone.
6. Connect existing acquisition paths to a SINGLE gate; deduplicate scheduled
   event IDs, implement expiry/no catch-up and authenticated manual triggers.
7. Test ZARJPY first; keep other currency interfaces and schedules unchanged.
8. Verify two real fresh publications during an open market before declaring
   mirror acceptance or extending the prototype.
