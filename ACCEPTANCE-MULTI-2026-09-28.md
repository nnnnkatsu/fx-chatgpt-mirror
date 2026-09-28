# USDJPY / MXNJPY passive mirror acceptance ? 2026-09-28

## Deployment

Installed at 06:38:01 UTC (15:38 JST). Runtime release:
`ca08ec51e92e7f1718982abcc9a97026c47e50dc`.
Installer: `c9ab4a566bc89e859f505daeab6cd82b93d516df`.
PHP lint and isolated tests for all three pairs passed before live replacement.
Only the existing passive response hook was broadened; original API routes,
response bodies, launcher and PATH nonce were preserved. GBPUSD is excluded.
The private runtime remains `/home/drexworld/fx-mirror/`.
Backup: `before-ca08ec51e92e7f1718982abcc9a97026c47e50dc/` within that directory.
Installed proxy SHA256:
`a42a09fea4a1e170af8a0f16f9943dcf3e8450573be0efdebb1acbbe2a5380f7`.

Cron was restored to `python3 /home/drexworld/fx-mirror/sakura_runner.py`
every two minutes. This reads three local cache files only; it never acquires
market data. The GitHub token remains in the existing private cron environment.
No token or private source response was added to this repository.

## Live acceptance

Exactly one new analysis request per added currency was issued for this
acceptance, 99 seconds apart. These are requests, NOT measured Twelve Data credits.
Both used freshly generated existing launcher links. The server cron published
both snapshots; no developer pushed the data files manually.

| Pair | fetched_at_utc | mirrored_at_utc | Data commit |
|---|---|---|---|
| USDJPY | 2026-09-28T06:39:28.611Z | 2026-09-28T06:40:00.098Z | 4b285112b3539d4e747b5693e6ce5a3d15db6030 |
| MXNJPY | 2026-09-28T06:41:07.529Z | 2026-09-28T06:42:00.158Z | 0f3dabc4a91fa4d12a48b653a34b0b25d91b71a1 |

Anonymous HTTPS GET returned HTTP 200 for both main-branch RAW files.
The original analysis fields/values were compared in full and remained equal.
Both passed the six-timeframe freshness checks at acceptance time.
The connected GitHub reader also returned both published snapshots.
At 06:44 UTC the server reported MXN unchanged, with the same mirror timestamp
and blob SHA, demonstrating local deduplication.

- https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/usdjpy.json
- https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/mxnjpy.json

Snapshots expire normally. Acceptance at a particular time is not a claim that
these files remain live indefinitely. No automatic prefetch has been enabled.
Without a successful existing acquisition request, the passive mirror cannot
refresh itself. Readers must reject expired snapshots, including a recent
mirror timestamp paired with an old source timestamp.

## Remaining work

Active acquisition before scheduled analysis and global quota enforcement still
require inspection of the Worker collection cost and all callers sharing the key.
The account limit is 800 credits/day and 8/minute; no global guarantee is claimed.
See QUOTA_PLAN.md. Existing ChatGPT tasks were requested to retain their trading
rules and use bounded Sakura access followed by the corresponding GitHub fallback.
33 offline Python tests passed, including cross-pair rejection, API file routing,
independent checkpoints, stale-data rejection, secret filtering and GitHub retries.
