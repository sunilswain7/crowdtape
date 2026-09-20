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
import json, math, os, sys, time, datetime, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import net

KEY = os.environ.get("CMC_API_KEY")
if not KEY:
    sys.exit("CMC_API_KEY not set")

BASE = "https://pro-api.coinmarketcap.com"
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = pathlib.Path(os.environ.get("CROWDTAPE_DATA_DIR") or ROOT / "data")
DATA.mkdir(exist_ok=True)

UNIVERSE = 200  # listings/latest is priced per 200 data points, so this costs 1 credit

# --- holder counts ----------------------------------------------------------
# `/v1/dex/holders/count` is how many distinct wallets hold a token. It is the only
# actual measurement of crowd size reachable on this plan - not a proxy like turnover -
# and CoinMarketCap gates `/v1/dex/holders/trend/list` (403, measured), so the series
# does not exist anywhere unless somebody records the counts. That is the whole idea.
#
# It costs 1 credit per token and 137 of the top 200 carry a contract address, so polling
# them all every ten minutes would be 19,728 credits a day against a 15,000/month ceiling.
# Wallet counts move over hours, not minutes, so they are polled on a slow cycle instead:
# HOLDERS_N tokens every HOLDERS_EVERY snapshots. 50 tokens every 18 cycles (3 hours) is
# 400 credits a day, inside the 603/day that is spare after the main recorder.
#
# Parameter names are `platform` and `tokenAddress`, camelCase where the rest of the API
# is snake_case. Five snake_case spellings returned a bare "Missing required parameter";
# these came from a working call in a public repository and were then verified live.
HOLDERS_N = int(os.environ.get("HOLDERS_N", "50"))
RATE_SLEEP = 1.3   # 50 requests/minute on Basic, measured from /v1/key/info


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
     {"limit": str(UNIVERSE), "convert": "USD", # Measured: naming any aux field drops `platform`, and `platform` is where the
     # contract address lives that the holder pass needs. `tags` returns with or
     # without aux, so the only reason this parameter exists is to keep platform.
     "aux": "cmc_rank,tags,platform"}),
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


def _r(x, sig=6):
    """Round to significant figures. Prices span 1e-9 to 1e5, so decimal places are
    the wrong unit; this halves the stored size without losing anything the engine reads."""
    if not isinstance(x, (int, float)) or isinstance(x, bool) or x == 0:
        return x
    try:
        return round(x, -int(math.floor(math.log10(abs(x)))) + (sig - 1))
    except (ValueError, OverflowError):
        return x


def thin(stream, data):
    """Keep what the engine reads and discard the rest.

    An untrimmed snapshot measured 133 KB, half of it `fiats` arrays on exchange records
    that nothing looks at. At one snapshot every ten minutes that is 19 MB a day into a
    git repository, so the payloads are cut down here rather than at read time. Field
    names below are taken from observed responses - see docs/payload-shapes.md."""
    if data is None:
        return None

    if stream == "listings" and isinstance(data, list):
        out = []
        for c in data:
            q = (c.get("quote", {}) or {}).get("USD", {}) or {}
            tags = c.get("tags")
            pf = c.get("platform") or {}
            out.append({"id": c.get("id"), "s": c.get("symbol"), "r": c.get("cmc_rank"),
                        # chain slug and contract address, for the holder pass
                        "pf": pf.get("slug"), "ca": pf.get("token_address"),
                        # None distinguishes "not a stablecoin" from "tags not returned"
                        "st": ("stablecoin" in tags) if isinstance(tags, list) else None,
                        "p": _r(q.get("price")), "mc": _r(q.get("market_cap")),
                        "v": _r(q.get("volume_24h")), "c1": _r(q.get("percent_change_1h"), 4),
                        "c24": _r(q.get("percent_change_24h"), 4),
                        "c7": _r(q.get("percent_change_7d"), 4)})
        return out

    if stream == "liquidations" and isinstance(data, dict):
        # {"cryptocurrencies": [{crypto_id, symbol, cmc_rank, quotes: [{...}]}], total_size}
        # The row-level crypto_id is the asset (BTC = 1). The crypto_id inside `quotes`
        # is the convert currency (USD = 2781) and is not the asset.
        rows = []
        for c in data.get("cryptocurrencies", []) or []:
            q = (c.get("quotes") or [{}])[0]
            rows.append({"id": c.get("crypto_id"), "s": c.get("symbol"),
                         "r": c.get("cmc_rank"),
                         "l1": _r(q.get("long_liquidations_1h")),
                         "s1": _r(q.get("short_liquidations_1h")),
                         "l4": _r(q.get("long_liquidations_4h")),
                         "s4": _r(q.get("short_liquidations_4h")),
                         "l24": _r(q.get("long_liquidations_24h")),
                         "s24": _r(q.get("short_liquidations_24h"))})
        return {"rows": rows, "total_size": data.get("total_size"),
                "has_more": data.get("has_more")}

    if stream == "deriv_exchanges" and isinstance(data, dict):
        # Per-venue open interest, aggregated. This is market-wide leverage context, not
        # a per-asset signal, so only the total and the largest venues are worth keeping -
        # the raw response carries an 89-entry `fiats` array per exchange.
        venues = data.get("exchanges", []) or []
        total_oi = total_vol = 0.0
        top = []
        for e in venues:
            q = (e.get("quotes") or [{}])[0]
            oi = q.get("open_interest_usd") or 0.0
            vol = q.get("derivative_volume_usd") or 0.0
            total_oi += oi
            total_vol += vol
            top.append({"n": e.get("exchange_name"), "oi": _r(oi), "v": _r(vol)})
        top.sort(key=lambda x: x["oi"] or 0, reverse=True)
        return {"total_oi": _r(total_oi), "total_vol": _r(total_vol),
                "venues": len(venues), "top": top[:15]}

    if stream == "global" and isinstance(data, dict):
        q = (data.get("quote", {}) or {}).get("USD", {}) or {}
        return {k: _r(v) for k, v in {
            "total_market_cap": q.get("total_market_cap"),
            "total_volume_24h": q.get("total_volume_24h"),
            "altcoin_market_cap": q.get("altcoin_market_cap"),
            "stablecoin_market_cap": q.get("stablecoin_market_cap"),
            "derivatives_volume_24h": q.get("derivatives_volume_24h"),
            "btc_dominance": data.get("btc_dominance"),
            "eth_dominance": data.get("eth_dominance"),
            "btc_dominance_24h_change": data.get("btc_dominance_24h_percentage_change"),
            "active_cryptocurrencies": data.get("active_cryptocurrencies"),
        }.items()}

    if stream.startswith("most_visited") or stream == "trending_latest":
        if isinstance(data, list):
            # Shape UNVERIFIED - plan-gated since the key was issued. Whole records are
            # kept until one has been seen, because discarding the field the signal turns
            # out to depend on is the one mistake that cannot be undone after the fact.
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

# --- holder pass, on the slow cycle ----------------------------------------
if os.environ.get("CROWDTAPE_HOLDERS") == "1":
    listings = (snapshot["streams"].get("listings") or {}).get("data") or []
    targets = [c for c in listings if c.get("pf") and c.get("ca")][:HOLDERS_N]
    rows, misses = [], {}
    print(f"\n  holder pass: {len(targets)} tokens")
    for c in targets:
        r = call("/v1/dex/holders/count",
                 {"platform": c["pf"], "tokenAddress": c["ca"]})
        total_credits += r.get("credits") or 0
        if r["http"] == 200 and isinstance(r.get("data"), dict):
            n = r["data"].get("count")
            rows.append({"id": c["id"], "s": c["s"], "pf": c["pf"],
                         "n": int(n) if n is not None else None})
        else:
            # Not every chain CoinMarketCap lists is a chain its DEX index covers -
            # hyperliquid answers "Parameter error". Record which, rather than dropping it.
            misses[c["s"]] = r.get("error", f"http {r['http']}")[:60]
        time.sleep(RATE_SLEEP)
    out_h = DATA / f"holders-{stamp:%Y-%m-%d}.jsonl"
    with out_h.open("a") as f:
        f.write(json.dumps({"at": stamp.isoformat(), "holders": rows,
                            "unavailable": misses}, separators=(",", ":")) + "\n")
    print(f"  holders: {len(rows)} recorded, {len(misses)} unavailable "
          f"-> {out_h.name}")

snapshot["credits"] = total_credits
out = DATA / f"{stamp:%Y-%m-%d}.jsonl"
with out.open("a") as f:
    f.write(json.dumps(snapshot, separators=(",", ":")) + "\n")

lines = sum(1 for _ in out.open())
print(f"\nappended to {out.name}  ({lines} snapshots today, {total_credits} credits this run)")
