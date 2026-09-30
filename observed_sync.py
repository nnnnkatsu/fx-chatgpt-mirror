"""Safe local diagnostics. No market-data requests, bodies or credentials logged."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import mirror
from cache_sync import atomic_json, sync_once, MAX_BYTES


def append_log(root, event):
    path = Path(root) / "mirror-events.jsonl"
    if path.exists() and path.stat().st_size > 1000000:
        os.replace(path, path.with_suffix(".jsonl.1"))
    with path.open("a", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        stream.write(json.dumps(event, allow_nan=False) + "\n")


def observed_sync(root, token, pair, now=None, trigger="cron_fallback"):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    state = {"trigger": trigger, "pair": pair, "started_at_utc": mirror.stamp(now), "upstream_requests": 0,
             "github_requests": 0, "update_attempted": False, "commit_sha": None}
    events = []
    def audit(event):
        safe = {"event": "github_http", "method": event["method"], "http_code": int(event["http_code"])}
        for key in ("remote_blob_sha", "commit_sha"):
            value = event.get(key)
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40,64}", value):
                safe[key] = value
                state[key] = value
        state["github_requests"] += 1
        state["update_attempted"] |= safe["method"] == "PUT"
        state["github_http_code"] = safe["http_code"]
        events.append(dict(safe, at_utc=mirror.stamp(datetime.now(timezone.utc))))
    append_log(root, dict(state, event="start"))
    try:
        source = root / "cache" / (pair.lower() + "-analysis.json")
        if source.exists():
            with source.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("oversized local source")
            data = json.loads(raw)
            mirror.no_secrets(data)
            fetched = mirror.utc(data["fetched_at_utc"])
            state.update(local_fetched_at_utc=mirror.stamp(fetched),
                         local_cache_age_seconds=round((now-fetched).total_seconds(), 3),
                         local_cache_mtime_utc=mirror.stamp(datetime.fromtimestamp(source.stat().st_mtime,timezone.utc)),
                         local_source_sha256=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest())
        state.update(sync_once(root, token, now, pair, audit=audit))
    except Exception as exc:
        message = str(exc)
        state.update(ok=False, error_type=type(exc).__name__)
        if message == "stale or future fetch":
            state.update(stage="awaiting_fresh_source", reason="local_cache_expired_or_future")
        elif message == "stale candle":
            state.update(stage="awaiting_fresh_source", reason="source_candles_expired")
        elif re.fullmatch(r"GitHub HTTP [0-9]{3}", message):
            state.update(stage="github_publish_failed", reason=message.replace(" ", "_"))
        elif message == "GitHub transport failure":
            state.update(stage="github_publish_failed", reason="github_transport_failure")
        elif message == "missing GitHub token":
            state.update(stage="configuration_error", reason="missing_github_credential")
        else:
            state.update(stage="source_or_publish_validation_failed", reason="validation_or_io_failure")
    health_path = root / ("health-" + pair.lower() + ".json")
    try:
        previous = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
    except (ValueError, OSError):
        previous = {}
    blocked = state["stage"] in ("awaiting_fresh_source", "awaiting_local_source")
    failed = not state.get("ok") and not blocked
    state["consecutive_failures"] = previous.get("consecutive_failures", 0) + 1 if failed else 0
    state["consecutive_source_waits"] = previous.get("consecutive_source_waits", 0) + 1 if blocked else 0
    state["alert"] = "source_not_refreshing" if blocked else ("publish_or_validation_failure" if failed else None)
    state["last_success"] = ({k:state.get(k) for k in ("fetched_at_utc", "mirrored_at_utc", "blob_sha", "commit_sha")}
                             if state["stage"] == "complete" else previous.get("last_success"))
    state["finished_at_utc"] = mirror.stamp(datetime.now(timezone.utc))
    state["github_events"] = events
    atomic_json(health_path, state)
    append_log(root, dict(state, event="finish"))
    return state
