# ZARJPY real-data acceptance: 2026-09-28

The user authorized a real test and confirmed limits of 800 credits/day and
8 credits/minute. The test issued exactly TWO Sakura ZARJPY analysis requests,
159 seconds apart. Actual Twelve Data credit debit is not yet measured; one
analysis may fan out into several upstream requests. No other pair was queried.

| Test | Source fetched_at_utc | _mirror.mirrored_at_utc | Data commit |
|---|---|---|---|
| 1 | 2026-09-28T01:09:05.532Z | 2026-09-28T01:10:00.074Z | cb743673368d2896b651395892ee6bf0e7ce6ad6 |
| 2 | 2026-09-28T01:11:44.893Z | 2026-09-28T01:12:00.091Z | bff4f3e9e7bd40444163d2ba53127888a5e07db6 |

Both publications came from server CRON, not local manual git uploads.
The server reported stage=complete and upstream_requests=0 for mirror execution.
This proves the mirror path performs no new market-data fetch; it is not a
measurement of all account-wide Twelve Data usage.

Second GitHub blob SHA: 32215ffce8f99a598e39d67965369fcd15bb1326.
Second original source canonical SHA-256:
e3cd70ebe3306e22e8766b14bdf39c211b85d9da3082723713c560af6d418e09

The second published JSON was compared against the privately saved original:
every original field/value matched, and freshness validation passed at test time.
Six timeframes were present. Source has no generated_at_utc, retained as null.
Token write permissions and real response capture are now proven.

Anonymous HTTP returned 200 for public RAW (including latest commit-pinned RAW).
GitHub connector also returned both snapshots; the second was verified using the
commit-pinned raw URL to avoid stale main/CDN content.
Ordinary web reader returned Cache miss during this test. Connector success
MUST NOT be represented as ordinary web-reader stability. Consumers must continue
checking source timestamps, including when GitHub main/CDN returns older content.

Public main:
https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/zarjpy.json

The two-publication ZARJPY transport acceptance is complete. This does not enable
continuous market-data collection, schedule prefetch, automatic ChatGPT task
edits, authenticated manual triggers, or mirrors for other pairs.
Only normal successful Sakura ZARJPY analysis requests produce new local input.
Snapshots age normally when no new requests occur.

collection-policy.example.json now records confirmed 8/minute and 800/day
limits, but enabled=false and all_upstream_callers_gated=false remain intact.
Per-analysis upper-bound cost, other existing callers, current usage, detection
schedule/timezone and any monthly constraint still require verification before
turning on active scheduling.
