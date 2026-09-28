"""Publish an existing Sakura ZARJPY analysis; Python 3.9+, no dependencies."""
import argparse
import base64
import copy
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://api.github.com/repos/nnnnkatsu/fx-chatgpt-mirror/contents/data/zarjpy.json"
INTERVALS = {"1min": 60, "5min": 300, "15min": 900, "1h": 3600, "4h": 14400, "1day": 86400}

def utc(value, daily=False):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    if daily and re.fullmatch(r"\d{4}-\d{2}-\d{2}Z", value):
        value = value[:-1] + "T00:00:00Z"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
        raise ValueError("explicit UTC timestamp required")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def stamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")

def no_secrets(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub("[^a-z0-9]", "", key.lower())
            if any(word in normalized for word in ("apikey", "token", "password", "passwd", "secret", "authorization", "cookie", "credential")):
                raise ValueError("credential-like field rejected")
            no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            no_secrets(item)
    elif isinstance(value, str):
        if re.search(r"(github_pat_|gh[pousr]_|-----BEGIN .*PRIVATE KEY|Bearer\s|[?&](api_?key|token|password)=|https?://[^/\s]+:[^/\s]+@)", value, re.I):
            raise ValueError("credential-like value rejected")

def finite_number(value):
    return type(value) in (float, int) and math.isfinite(value)

PAIRS = {"ZARJPY": "ZAR/JPY", "USDJPY": "USD/JPY", "MXNJPY": "MXN/JPY"}

def validate(data, now=None, pair="ZARJPY"):
    now = now or datetime.now(timezone.utc)
    no_secrets(data)
    if data.get("ok") is not True or data.get("type") != "analysis":
        raise ValueError("not a successful analysis response")
    if pair not in PAIRS or data.get("symbol") != PAIRS[pair] or data.get("pair", pair) != pair:
        raise ValueError("wrong pair")
    if data.get("source") != "Twelve Data":
        raise ValueError("unexpected upstream source")
    if not finite_number(data.get("price")) or data["price"] <= 0:
        raise ValueError("invalid price")
    fetched = utc(data["fetched_at_utc"])
    if not 0 <= (now - fetched).total_seconds() <= 300:
        raise ValueError("stale or future fetch")
    generated = data.get("generated_at_utc")
    if generated is not None:
        generated = utc(generated)
        if not fetched <= generated <= now or (now - generated).total_seconds() > 300:
            raise ValueError("invalid source generation time")
    for tf, interval in INTERVALS.items():
        part = data["analysis"][tf]
        if part.get("timezone") != "UTC":
            raise ValueError("unknown candle timezone")
        latest = utc(part["latest_candle_at_utc"], daily=tf == "1day")
        current = utc(part["current_candle"]["datetime_utc"], daily=tf == "1day")
        if latest != current or latest > fetched:
            raise ValueError("inconsistent candle timestamp")
        age = (now - latest).total_seconds()
        if not 0 <= age <= interval + 300:
            raise ValueError("stale candle")
        recorded_age = part["candle_age_seconds"]
        # Source computes ages while building the response. Allow 60s assembly.
        if not finite_number(recorded_age) or recorded_age < 0 or abs(recorded_age - (fetched - latest).total_seconds()) > 60:
            raise ValueError("inconsistent recorded candle age")
        if not isinstance(part.get("candles"), list) or not part["candles"] or not isinstance(part.get("indicators"), dict) or not part["indicators"]:
            raise ValueError("missing candle history or indicators")
    return data

def build(data, now=None, pair="ZARJPY"):
    now = now or datetime.now(timezone.utc)
    validate(data, now, pair)
    if "_mirror" in data:
        raise ValueError("input must be the original Sakura response")
    result = copy.deepcopy(data)
    result.setdefault("pair", pair)
    result.setdefault("generated_at_utc", None)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    result["_mirror"] = {
        "schema_version": "2.0", "via": "sakura-v3.1",
        "mirrored_at_utc": stamp(now),
        "source_generated_at_available": data.get("generated_at_utc") is not None,
        "source_sha256": hashlib.sha256(canonical).hexdigest(),
        "mode": "snapshot",
    }
    return result

def api(method, token, body=None, pair="ZARJPY"):
    if pair not in PAIRS:
        raise ValueError("unsupported pair")
    endpoint = API.replace("zarjpy.json", pair.lower() + ".json")
    data = None if body is None else json.dumps(body).encode()
    request = Request(endpoint + ("?ref=main" if method == "GET" else ""), data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "sakura-zarjpy-mirror",
                 "X-GitHub-Api-Version": "2026-03-10"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def publish(payload, token, pair="ZARJPY"):
    for attempt in range(3):
        try:
            validate(payload, pair=pair)
            try:
                current = api("GET", token, pair=pair)
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                current = None
            body = {"message": "Update " + pair + " analysis snapshot", "branch": "main"}
            if current:
                old = json.loads(base64.b64decode(current["content"]))
                if old.get("fetched_at_utc") and utc(old["fetched_at_utc"]) >= utc(payload["fetched_at_utc"]):
                    print("Skipped: same or newer source fetch already published")
                    return
                body["sha"] = current["sha"]
            body["content"] = base64.b64encode((json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()).decode()
            api("PUT", token, body, pair=pair)
            print("Published data/" + pair.lower() + ".json")
            return
        except HTTPError as exc:
            retryable = exc.code in (409, 429, 500, 502, 503, 504)
            if not retryable or attempt == 2:
                raise RuntimeError("GitHub HTTP " + str(exc.code)) from None
            try:
                delay = min(60, max(2 ** attempt, int(exc.headers.get("Retry-After", "0"))))
            except (ValueError, AttributeError):
                delay = 2 ** attempt
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("GitHub transport failure") from None
            delay = 2 ** attempt
        time.sleep(delay)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", help="existing ZARJPY analysis JSON file; no credentials")
    parser.add_argument("--output", help="optional mirror preview file")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--public-export-reviewed", action="store_true",
                        help="confirm that this source contains only reviewed public market data")
    args = parser.parse_args()
    if not args.public_export_reviewed:
        raise ValueError("review the public export before use")
    original = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    payload = build(original)
    if args.output:
        if Path(args.output).resolve() == Path(args.analysis).resolve():
            raise ValueError("cannot overwrite source")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, target)
    if args.publish:
        token = os.environ.get("FX_MIRROR_GITHUB_TOKEN")
        if not token:
            raise ValueError("missing process environment token")
        publish(payload, token)
    elif not args.output:
        print("Validated source analysis")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Mirror failed (" + type(exc).__name__ + "); inspect private configuration; no data logged.", file=sys.stderr)
        sys.exit(1)
