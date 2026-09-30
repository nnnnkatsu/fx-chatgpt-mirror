# Cache event delivery (Sakura)

When the existing capture hook writes changed USDJPY, ZARJPY or MXNJPY analysis,
it starts a finite detached Python publisher for that pair. The HTTP response
is not delayed by GitHub requests. No market endpoint is called by this path.
Exact duplicate response bodies and older snapshots do not launch publication.
GBPUSD, launcher, nonce rules and proxy routes are unchanged.

The event process shares sync.lock with the existing 2-minute cron and uses the
same source validation, duplicate checkpoint, GitHub retries and safe diagnostics.
A busy lock skips the event; failed publication leaves the checkpoint unchanged.
The next cron retries the latest local cache. There is no daemon, polling loop,
additional cron or automatic market-data retry. An event has the existing
90-second deadline. Disabled PHP exec leaves the original cron operational.

Cron provisions its existing FX_MIRROR_GITHUB_TOKEN into
/home/drexworld/fx-mirror/github-credential.json (0600, parent 0700, outside www).
The event reads this private file; the token is never put in a URL, command line,
public status, log or repository. Updating the existing cron environment refreshes
this private copy on the next run. Keep both copies restricted to this account.
The installer records the cron Python executable in event-python.txt.

Public fx-mirror-status.json distinguishes cache_event from cron_fallback;
per-pair health includes fetched time, mirrored time and commit SHA. A later cron
may overwrite the top-level trigger; per-pair logs retain the publication result.
The JSON schedule_seconds=120 describes fallback cadence, not event latency;
delivery=cache-event-with-cron-fallback identifies the new mechanism.

Roll back capture.php, sakura_runner.py and cache_sync.py from the private
before-event-<release> backup, under sync.lock; the unchanged cron remains valid.
Do not restore or publish private credential files into the web directory.

Freshness gates remain unchanged. Event delivery reduces copying delay but cannot
make an already-old upstream candle new or guarantee scheduler/network latency.
