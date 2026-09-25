"""Sakura ZARJPY mirror: Python 3.9+, standard library only.
Input contract and deployment limitations are documented in README.md.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SOURCE = "sakura-v3.1"
API = "https://api.github.com/repos/nnnnkatsu/fx-chatgpt-mirror/contents/zarjpy.json"
INTERVALS = {"1min": 60, "5min": 300, "15min": 900, "1h": 3600, "4h": 14400, "1day": 86400}

def utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamps must be explicit UTC strings ending in Z")
    return datetime.fromisoformat(value[:-1] + "+00:00")

def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def no_secrets(value):
    # Defense in depth only: a reviewed public-data exporter is still required.
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub("[^a-z0-9]", "", key.lower())
            if any(word in normalized for word in ("apikey", "token", "password", "secret", "authorization", "cookie", "credential")):
                raise ValueError("credential-like field rejected")
            no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            no_secrets(item)
    elif isinstance(value, str):
        if re.search(r"(github_pat_|gh[pousr]_|-----BEGIN .*PRIVATE KEY|Bearer\s|[?&](api_?key|token|password)=|https?://[^/\s]+:[^/\s]+@)", value, re.I):
            raise ValueError("credential-like value rejected")

def build(analysis, metadata, now=None):
    now = now or datetime.now(timezone.utc)
    no_secrets(analysis)
    if not isinstance(analysis, dict) or not analysis:
        raise ValueError("analysis must be a nonempty public JSON object")
    if metadata.get("source") != SOURCE or metadata.get("pair") != "ZARJPY":
        raise ValueError("source/pair mismatch")
    if metadata.get("public_export_reviewed") is not True:
        raise ValueError("public export must be reviewed before publication")
    # These must describe this exact analysis export, not the uploader clock.
    generated = utc(metadata["generated_at_utc"])
    fetched = utc(metadata["fetched_at_utc"])
    if not (fetched <= generated <= now):
        raise ValueError("invalid timestamp order or future timestamp")
    if (now - fetched).total_seconds() > 300 or (now - generated).total_seconds() > 300:
        raise ValueError("source export is stale")
    candles = metadata["candles"]
    if not all(tf in candles for tf in ("1min", "1h", "4h", "1day")):
        raise ValueError("required 1min/H1/H4/D1 freshness is missing")
    freshness = {}
    for tf, item in candles.items():
        if tf not in INTERVALS or item.get("timestamp_semantics") != "open":
            raise ValueError("unknown interval or candle timestamp semantics")
        opened = utc(item["latest_candle_at_utc"])
        age = (now - opened).total_seconds()
        # Both currently forming and latest closed bars accepted; consumers must
        # use is_closed when selecting candles for close-based trading rules.
        if type(item.get("is_closed")) is not bool:
            raise ValueError("is_closed must be boolean")
        if opened > fetched or age < 0 or age > INTERVALS[tf] + 300:
            raise ValueError("candle freshness invalid")
        if item["is_closed"] and (fetched - opened).total_seconds() < INTERVALS[tf]:
            raise ValueError("candle cannot yet be closed")
        freshness[tf] = {
            "latest_candle_at_utc": stamp(opened),
            "timestamp_semantics": "open",
            "is_closed": item["is_closed"],
            "candle_age_seconds": int(age),
        }
    latest = freshness["1min"]
    return {
        "schema_version": "1.0", "pair": "ZARJPY", "source": SOURCE,
        "status": "live", "tradable": False,
        "generated_at_utc": stamp(generated), "fetched_at_utc": stamp(fetched),
        "latest_candle_at_utc": latest["latest_candle_at_utc"],
        "candle_age_seconds": latest["candle_age_seconds"],
        "mirrored_at_utc": stamp(now), "freshness_by_timeframe": freshness,
        "analysis": analysis,
    }

def api(method, token, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(API + ("?ref=main" if method == "GET" else ""), data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "sakura-zarjpy-mirror",
                 "X-GitHub-Api-Version": "2026-03-10"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def publish(payload, token):
    # Serial GET-SHA/PUT; never force-push. Re-read after conflicts/timeouts.
    for attempt in range(3):
        try:
            if (datetime.now(timezone.utc) - utc(payload["fetched_at_utc"])).total_seconds() > 300:
                raise ValueError("payload became stale before upload")
            try:
                current = api("GET", token)
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                current = None
            body = {"message": "Update ZARJPY analysis mirror", "branch": "main"}
            if current:
                old = json.loads(base64.b64decode(current["content"]))
                old_generated = old.get("generated_at_utc")
                if old_generated and utc(old_generated) >= utc(payload["generated_at_utc"]):
                    print("Skipped: same or newer source export already published")
                    return
                body["sha"] = current["sha"]
            body["content"] = base64.b64encode((json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")).decode("ascii")
            api("PUT", token, body)
            print("Published zarjpy.json")
            return
        except HTTPError as exc:
            if exc.code not in (409, 429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError("GitHub upload failed: HTTP " + str(exc.code)) from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("GitHub transport failed") from None
        time.sleep(2 ** attempt)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("export", help="private reviewed export bundle: {analysis, metadata}")
    parser.add_argument("--output", help="write a local preview; never point at original analysis")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    bundle = json.loads(Path(args.export).read_text(encoding="utf-8"))
    payload = build(bundle["analysis"], bundle["metadata"])
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        if Path(args.output).resolve() == Path(args.export).resolve():
            raise ValueError("output must not overwrite source")
        Path(args.output).write_text(encoded, encoding="utf-8")
    if args.publish:
        token = os.environ.get("FX_MIRROR_GITHUB_TOKEN")
        if not token:
            raise ValueError("FX_MIRROR_GITHUB_TOKEN environment variable is missing")
        publish(payload, token)
    elif not args.output:
        print("Validated; use --output or --publish")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not echo input, request headers, tokens, URLs or API response bodies.
        print("Mirror failed (" + type(exc).__name__ + "); previous remote data retained.", file=sys.stderr)
        sys.exit(1)
