"""ZARJPY passive mirror runner. No market-data HTTP requests."""
import signal
import json
import stat
import sys
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

def credential(root, event=False):
    """Cron provisions the existing token privately; PHP never handles its value."""
    path = root / "github-credential.json"
    token = None if event else os.environ.get("FX_MIRROR_GITHUB_TOKEN")
    if token:
        atomic_json(path, {"token": token})
        return token
    if not path.exists():
        return None
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or (os.name != "nt" and
            (info.st_mode & 0o077 or info.st_uid != os.getuid())):
        raise ValueError("unsafe credential file")
    value = json.loads(path.read_text(encoding="utf-8")).get("token")
    return value if isinstance(value, str) and value else None


def run(pair=None):
    if pair is not None and pair not in mirror.PAIRS:
        raise ValueError("unsupported pair")
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
        token = credential(ROOT, event=pair is not None)
        results = {}
        for current_pair in ([pair] if pair else mirror.PAIRS):
            signal.alarm(90)
            try:
                results[current_pair] = observed_sync(ROOT, token, current_pair, trigger="cache_event" if pair else "cron_fallback")
            except Exception as exc:
                results[current_pair] = {"ok": False, "stage": "local_cache_or_publish",
                                 "upstream_requests": 0, "error_type": type(exc).__name__}
            finally:
                signal.alarm(0)
        for other in mirror.PAIRS:
            if other not in results:
                try:
                    results[other] = json.loads((ROOT / ("health-" + other.lower() + ".json")).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    results[other] = {"ok": False, "stage": "not_checked"}
        status = {"trigger": "cache_event" if pair else "cron_fallback", "event_pair": pair,
                  "ok": all(v.get("ok") for v in results.values()),
                  "stage": "passive_cache_check", "upstream_requests": 0, "schedule_seconds": 120}
        status["pairs"] = results
        write_status(status)
        return 0

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and (len(args) != 2 or args[0] != "--event" or args[1] not in mirror.PAIRS):
        raise SystemExit(2)
    raise SystemExit(run(args[1] if args else None))
