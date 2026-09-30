# Event sync acceptance: 2026-09-30

Runtime release: `0e0db60a3581edf4bf269f86a32b15b8df43c734`.
Prefetch configuration: `38a090d33d52d531d504a066c26be617e62404d8`; Cloudflare build succeeded at 09:56:50 UTC.

| Pair | Source fetched (UTC) | Mirror snapshot time (UTC) | Publish verified complete (UTC) | Commit |
| --- | --- | --- | --- | --- |
| ZARJPY | 2026-09-30T09:55:00.833Z | 2026-09-30T09:55:00.959Z | 2026-09-30T09:55:02.927Z | `0206777a98a30c6f7cc7045082f37f2999417dc5` |
| MXNJPY | 2026-09-30T09:57:16.188Z | 2026-09-30T09:57:16.315Z | 2026-09-30T09:57:18.324Z | `69069768b5e6ad753f839be41aec3536b5e7680c` |
| USDJPY | 2026-09-30T10:04:24.768Z | 2026-09-30T10:04:25.830Z | 2026-09-30T10:04:27.581Z | `093cafb5149c35059c4b285a154c7490598045b7` |

ZAR and MXN used one manual launcher analysis each, separated by over 75 seconds (at most 14 scheduled-account credits in total for these tests). USD was the normal 19:04 JST scheduled prefetch; no manual USD collection. The mirror processes themselves made zero upstream market requests.

The original every-two-minute cron was restored after installation and diagnostics and confirmed active at 10:00 and 10:02 UTC. Event sync and cron use the same lock, validators and publication checkpoints. Sakura index.php SHA-256 remained a42a09fea4a1e170af8a0f16f9943dcf3e8450573be0efdebb1acbbe2a5380f7.

Tests: 40 Python tests passed, one Unix-only negative permission test skipped locally on Windows; installer verified actual credential mode 0600. Server PHP lint and isolated background launches for all three currencies passed. Worker schedule/DST/full-analysis regressions passed.

Historical MXN incident: at 03:14 and 03:16 UTC, the cache had fetched_at_utc=03:12:36.193Z but validation rejected source_candles_expired before any GitHub HTTP request. This was not a GitHub token or push failure. The historical log does not identify which timeframe.

These are delivery acceptance results, not live trading signals or a guarantee that future upstream candles are fresh. Keep all current source/candle freshness gates. Mirrored_at_utc is the snapshot construction time; finished_at_utc records completion of remote verification.

Anonymous HTTPS GETs to the pinned public RAW snapshots for all three pairs returned HTTP 200 without cookies, login or authorization headers. The USD 5-minute candle was 10:00 UTC, within the unchanged threshold at the 19:05 JST check time.
