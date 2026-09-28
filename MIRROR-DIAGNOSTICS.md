# Mirror diagnosis

The public heartbeat at 2026-09-28T10:18:00.094Z proves cron was still running.
It reported ValueError for each pair, but the old error label combined source
validation and GitHub publication. It cannot identify a token problem.

The confirmed USD publication remains fetched 2026-09-28T06:39:28.611Z,
mirrored 2026-09-28T06:40:00.098Z, data commit
4b285112b3539d4e747b5693e6ce5a3d15db6030. Current local server cache inspection
is still required before classifying the root cause.

## Prepared changes (not yet deployed)

- observed_sync.py: timestamp and canonical hash of local source; distinguishes
  expired cache/candles, missing cache, configuration errors and GitHub failures.
- mirror.py and cache_sync.py: optional safe HTTP audit, remote blob/commit SHA;
  no HTTP response bodies, tokens or arbitrary exception text are logged.
- sakura_runner.py: per-pair diagnostics and accurate aggregate status instead
  of copying ZAR status to the top level. No market data requests are added.
- Private mirror-events.jsonl rotates at 1MB with one previous file; mode 0600.
  Per-pair health files retain last success and consecutive failure/source-wait
  counts. Every cron run retries eligible fresh data; failed publishes never
  mark a local source as successfully published.

37 offline tests pass. They include three different snapshots 120 seconds apart
under a simulated clock after a failed publish, and no network for stale data.
This is NOT a claim of three live successful publications.

Three real source-time advances require three genuine new source responses.
If the local source is old, the passive mirror must wait and report that fact;
it must never stamp old data as new or enable upstream polling as a workaround.
