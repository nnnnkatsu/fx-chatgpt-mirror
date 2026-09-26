"""Passive mirror: local files in, GitHub out; never fetch market data."""
import base64
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import mirror

MAX_BYTES = 1000000

def atomic_json(path, value, mode=0o600):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)

def sync_once(root, token, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    source_file = root / "cache" / "zarjpy-analysis.json"
    if not source_file.exists():
        return {"ok": False, "stage": "awaiting_local_source", "upstream_requests": 0}
    with source_file.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized local source")
    source = json.loads(raw)
    payload = mirror.build(source, now)
    source_hash = payload["_mirror"]["source_sha256"]
    checkpoint = root / "published.json"
    previous = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {}
    if previous.get("source_sha256") == source_hash:
        return dict(previous["status"], stage="unchanged", upstream_requests=0)
    if not token:
        raise ValueError("missing GitHub token")
    payload["_mirror"].update(mode="sakura-local-cache", schedule_seconds=120)
    mirror.publish(payload, token)
    remote = mirror.api("GET", token)
    actual = json.loads(base64.b64decode(remote["content"]))
    mirror.validate(actual)
    if mirror.utc(actual["fetched_at_utc"]) < mirror.utc(payload["fetched_at_utc"]):
        raise ValueError("remote did not advance")
    if actual["fetched_at_utc"] == payload["fetched_at_utc"] and actual.get("_mirror", {}).get("source_sha256") != source_hash:
        raise ValueError("remote source mismatch")
    status = {"ok": True, "stage": "complete", "upstream_requests": 0,
              "fetched_at_utc": actual["fetched_at_utc"],
              "mirrored_at_utc": actual.get("_mirror", {}).get("mirrored_at_utc"),
              "blob_sha": remote["sha"], "schedule_seconds": 120}
    atomic_json(checkpoint, {"source_sha256": source_hash, "status": status})
    return status
