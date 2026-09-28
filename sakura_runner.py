"""ZARJPY passive mirror runner. No market-data HTTP requests."""
import signal
from pathlib import Path
import os
from datetime import datetime, timezone
import mirror
from cache_sync import atomic_json
from observed_sync import observed_sync

ROOT = Path("/home/drexworld/fx-mirror")
STATUS = Path("/home/drexworld/www/fx-mirror-status.json")

def write_status(status):
    status["checked_at_utc"] = mirror.stamp(datetime.now(timezone.utc))
    atomic_json(STATUS, status, 0o644)

def timeout_handler(signum, frame):
    raise TimeoutError("run deadline")

def run():
    import fcntl  # Server is Unix; passive sync core is portable for offline tests.
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(ROOT, 0o700)
    with (ROOT / "sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        signal.signal(signal.SIGALRM, timeout_handler)
        results = {}
        for pair in mirror.PAIRS:
            signal.alarm(90)
            try:
                results[pair] = observed_sync(ROOT, os.environ.get("FX_MIRROR_GITHUB_TOKEN"), pair)
            except Exception as exc:
                results[pair] = {"ok": False, "stage": "local_cache_or_publish",
                                 "upstream_requests": 0, "error_type": type(exc).__name__}
            finally:
                signal.alarm(0)
        status = {"ok": all(v.get("ok") for v in results.values()),
                  "stage": "passive_cache_check", "upstream_requests": 0, "schedule_seconds": 120}
        status["pairs"] = results
        write_status(status)
        return 0

if __name__ == "__main__":
    raise SystemExit(run())
