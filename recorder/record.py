#!/usr/bin/env python3
"""
Crowdtape recorder.

CoinMarketCap discards its two most valuable datasets. There is no history endpoint
for attention (who is looking at what) and none for positioning (who is levered).
Both are latest-only. This appends one snapshot to data/YYYY-MM-DD.jsonl every run,
so the git history becomes a timestamped, publicly verifiable time series that does
not exist anywhere else - including inside CoinMarketCap.

Stdlib only. No database required to start. Runs on the free Basic tier: the
attention streams degrade to a recorded 403 rather than failing the run, and start
producing data the moment the hackathon upgrade lands.

Usage:  CMC_API_KEY=xxx python3 recorder/record.py
"""
import json, os, sys, time, datetime, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import net

KEY = os.environ.get("CMC_API_KEY")
if not KEY:
    sys.exit("CMC_API_KEY not set")

BASE = "https://pro-api.coinmarketcap.com"
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

UNIVERSE = 200  # listings/latest is priced per 200 data points, so this costs 1 credit

# axis: what each stream feeds. tier: lowest plan that can call it.
STREAMS = [
    # --- ATTENTION. Startup tier. The uncontested half. ---
    ("attention",   "most_visited_24h", "GET", "/v1/cryptocurrency/trending/most-visited",
     {"time_period": "24h", "limit": "100"}),
    ("attention",   "most_visited_7d",  "GET", "/v1/cryptocurrency/trending/most-visited",
     {"time_period": "7d", "limit": "100"}),
    ("attention",   "trending_latest",  "GET", "/v1/cryptocurrency/trending/latest",
     {"limit": "100"}),

    # --- POSITIONING. Works on Basic. Also has no history endpoint. ---
    ("positioning", "liquidations",     "GET", "/v5/derivatives/liquidations/cryptocurrency/list/latest", {}),
    ("positioning", "deriv_exchanges",  "GET", "/v5/exchange/derivatives/list", {}),

    # --- PRICE + CONTEXT. Works on Basic. The baseline every signal is measured against. ---
    ("price",       "listings",         "GET", "/v1/cryptocurrency/listings/latest",
     {"limit": str(UNIVERSE), "convert": "USD"}),
    ("context",     "global",           "GET", "/v1/global-metrics/quotes/latest", {}),
    ("context",     "fear_greed",       "GET", "/v3/fear-and-greed/latest", {}),
]


def call(path, params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}" + (f"?{qs}" if qs else "")
    t0 = time.time()
    code, raw = net.request(
        url, {"X-CMC_PRO_API_KEY": KEY, "Accept": "application/json"}, timeout=40)
    ms = int((time.time() - t0) * 1000)
    if code == 0:
        return {"http": 0, "error": (raw.decode("utf8", "ignore") or "unreachable")[:100], "ms": ms}
    try:
        payload = json.loads(raw)
    except Exception:
        return {"http": code, "error": "unparseable", "ms": ms}

    st = payload.get("status", {}) or {}
    # A path that does not exist answers HTTP 200 with error_code 500. Never treat
    # that as success - it silently records imaginary endpoints as working.
    if code == 200 and st.get("error_code") in (500, "500"):
        return {"http": code, "error": "PATH-ABSENT", "ms": ms}
    out = {"http": code, "ms": ms, "credits": st.get("credit_count")}
    if code == 200:
        out["data"] = payload.get("data")
    else:
        out["error"] = (st.get("error_message") or f"http {code}")[:120]
    return out


def thin(stream, data):
    """Keep the fields the engine reads. Full payloads would bloat the repo to
    nothing useful - the shape is stable and documented in docs/schema.md."""
    if data is None:
        return None
    if stream == "listings" and isinstance(data, list):
        return [{"id": c.get("id"), "s": c.get("symbol"), "r": c.get("cmc_rank"),
                 "p": (c.get("quote", {}).get("USD", {}) or {}).get("price"),
                 "mc": (c.get("quote", {}).get("USD", {}) or {}).get("market_cap"),
                 "v": (c.get("quote", {}).get("USD", {}) or {}).get("volume_24h"),
                 "c1": (c.get("quote", {}).get("USD", {}) or {}).get("percent_change_1h"),
                 "c24": (c.get("quote", {}).get("USD", {}) or {}).get("percent_change_24h"),
                 "c7": (c.get("quote", {}).get("USD", {}) or {}).get("percent_change_7d")}
                for c in data]
    if stream.startswith("most_visited") or stream == "trending_latest":
        if isinstance(data, list):
            # Rank is position in the returned list. Keep the whole record until the
            # probe tells us whether a magnitude field exists - we cannot afford to
            # discard the one field the signal might depend on.
            return [dict(rank=i + 1, **{k: v for k, v in c.items() if k != "quote"})
                    for i, c in enumerate(data[:100])]
    return data


stamp = datetime.datetime.now(datetime.timezone.utc)
snapshot = {"at": stamp.isoformat(), "streams": {}}
total_credits = 0

for axis, name, method, path, params in STREAMS:
    r = call(path, params)
    total_credits += r.get("credits") or 0
    rec = {"axis": axis, "path": path, "http": r["http"], "ms": r["ms"]}
    if "error" in r:
        rec["error"] = r["error"]
    else:
        rec["data"] = thin(name, r.get("data"))
    snapshot["streams"][name] = rec
    status = "ok" if r["http"] == 200 and "error" not in r else r.get("error", "?")
    print(f"  {name:<20} {r['http']:<5} {status}")
    time.sleep(0.2)

snapshot["credits"] = total_credits
out = DATA / f"{stamp:%Y-%m-%d}.jsonl"
with out.open("a") as f:
    f.write(json.dumps(snapshot, separators=(",", ":")) + "\n")

lines = sum(1 for _ in out.open())
print(f"\nappended to {out.name}  ({lines} snapshots today, {total_credits} credits this run)")
