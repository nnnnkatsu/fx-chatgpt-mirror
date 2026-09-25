"""Sakura cron runner. No credentials in this file. ZARJPY only."""
import fcntl
import signal
from urllib.request import Request, urlopen
from pathlib import Path
import os
import json
import time
import base64
from datetime import datetime, timezone
import mirror

ROOT = Path("/home/drexworld/fx-mirror")
STATUS = Path("/home/drexworld/www/fx-mirror-status.json")

def write_status(status):
    status["checked_at_utc"] = mirror.stamp(datetime.now(timezone.utc))
    temp = STATUS.with_suffix(".json.tmp")
    temp.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, 0o644)
    os.replace(temp, STATUS)

def fetch_analysis():
    url = "https://drexworld.sakura.ne.jp/fx/zarjpy/analysis/" + str(time.time_ns() // 1000000)
    req = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache",
                                "User-Agent": "Sakura-ZARJPY-Mirror/1.0"})
    with urlopen(req, timeout=18) as response:
        raw = response.read(1000001)
    if len(raw) > 1000000:
        raise ValueError("oversized source response")
    return json.loads(raw)

def timeout_handler(signum, frame):
    raise TimeoutError("run deadline")

def run():
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(ROOT, 0o700)
    with (ROOT / "sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(90)
        stage = "configuration"
        try:
            token = os.environ.get("FX_MIRROR_GITHUB_TOKEN")
            if not token:
                raise ValueError("missing token")
            stage = "sakura_fetch"
            source = fetch_analysis()
            stage = "freshness"
            payload = mirror.build(source)
            payload["_mirror"]["mode"] = "sakura-cron"
            payload["_mirror"]["schedule_seconds"] = 120
            stage = "github_publish"
            mirror.publish(payload, token)
            stage = "github_verify"
            remote = mirror.api("GET", token)
            actual = json.loads(base64.b64decode(remote["content"]))
            mirror.validate(actual)
            if mirror.utc(actual["fetched_at_utc"]) < mirror.utc(payload["fetched_at_utc"]):
                raise ValueError("remote did not advance")
            write_status({"ok": True, "stage": "complete",
                          "fetched_at_utc": actual["fetched_at_utc"],
                          "mirrored_at_utc": actual.get("_mirror", {}).get("mirrored_at_utc"),
                          "blob_sha": remote["sha"], "schedule_seconds": 120})
            return 0
        except Exception as exc:
            # Only fixed stages/type names, never response bodies or exception messages.
            write_status({"ok": False, "stage": stage, "error_type": type(exc).__name__})
            return 1
        finally:
            signal.alarm(0)

if __name__ == "__main__":
    raise SystemExit(run())
