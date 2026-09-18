#!/usr/bin/env python3
"""
CMC key capability probe. Answers three questions, in order of how badly we need them:

  1. What tier is this key ACTUALLY on?  /v1/key/info reports no tier name, only
     credit_limit_monthly. 15,000 = Basic. 450,000 = Startup. At least one hackathon
     participant measured Basic on 13 Sep despite the promised upgrade, so this is
     not a formality.
  2. Is trending/most-visited callable? The entire project plan depends on it.
  3. What shape is the most-visited payload? Rank-only or magnitude?

Trap this encodes (found the hard way by another participant): a path that does NOT
exist returns HTTP 200 with status.error_code 500 "The system is busy". Reading the
HTTP status alone records imaginary endpoints as working. Two control paths run every
time so a routing change surfaces as a failed control, not as quietly wrong results.

Usage:  CMC_API_KEY=xxx python3 scripts/probe.py
Costs:  well under 40 credits.
"""
import json, os, sys, time, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "recorder"))
import net

KEY = os.environ.get("CMC_API_KEY")
if not KEY:
    sys.exit("CMC_API_KEY not set.  Run:  CMC_API_KEY=your-key python3 scripts/probe.py")

BASE = "https://pro-api.coinmarketcap.com"
OUT = pathlib.Path(__file__).resolve().parent.parent / "probe-output"
OUT.mkdir(exist_ok=True)

TIERS = {15000: "Basic (free)", 150000: "Builder $29", 450000: "Startup $79",
         2000000: "Growth $299", 5000000: "Professional $699"}

# (group, label, path, params)  -- controls must stay first and last.
PROBES = [
    ("control",  "nonexistent path A",  "/v3/totally-made-up/xyz", {}),
    ("meta",     "key info",            "/v1/key/info", {}),

    ("ATTENTION","most visited 24h",    "/v1/cryptocurrency/trending/most-visited", {"time_period":"24h","limit":"20"}),
    ("ATTENTION","most visited 7d",     "/v1/cryptocurrency/trending/most-visited", {"time_period":"7d","limit":"20"}),
    ("ATTENTION","most visited 30d",    "/v1/cryptocurrency/trending/most-visited", {"time_period":"30d","limit":"20"}),
    ("ATTENTION","trending latest",     "/v1/cryptocurrency/trending/latest", {"limit":"20"}),
    ("ATTENTION","gainers losers",      "/v1/cryptocurrency/trending/gainers-losers", {"limit":"10"}),

    ("core",     "listings latest",     "/v1/cryptocurrency/listings/latest", {"limit":"5"}),
    ("core",     "listings v3",         "/v3/cryptocurrency/listings/latest", {"limit":"5"}),
    ("core",     "listings new",        "/v1/cryptocurrency/listings/new", {"limit":"5"}),
    ("core",     "listings historical", "/v1/cryptocurrency/listings/historical", {"date":"2026-09-01","limit":"5"}),
    ("core",     "global metrics",      "/v1/global-metrics/quotes/latest", {}),
    ("core",     "fear and greed",      "/v3/fear-and-greed/latest", {}),
    ("core",     "ohlcv historical",    "/v2/cryptocurrency/ohlcv/historical", {"symbol":"BTC","count":"3","interval":"1h","time_period":"hourly"}),
    ("core",     "quotes historical v3","/v3/cryptocurrency/quotes/historical", {"symbol":"BTC","count":"3","interval":"1h"}),

    ("POSITION", "deriv market-pairs",  "/v5/cryptocurrency/derivatives/market-pairs/list/latest", {"symbol":"BTC"}),
    ("POSITION", "liquidations by coin","/v5/derivatives/liquidations/cryptocurrency/list/latest", {}),
    ("POSITION", "deriv exchanges",     "/v5/exchange/derivatives/list", {}),

    ("rwa",      "rwa assets list",     "/v5/real-world-assets/assets/list", {"limit":"5"}),
    ("rwa",      "rwa quotes",          "/v5/real-world-assets/quotes/latest", {"limit":"5"}),

    ("gated",    "community trending",  "/v1/community/trending/token", {}),
    ("gated",    "content latest",      "/v1/content/latest", {"limit":"2"}),

    ("control",  "nonexistent path B",  "/v6/anything/here", {}),
]


def call(path, params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}" + (f"?{qs}" if qs else "")
    t0 = time.time()
    code, raw = net.request(
        url, {"X-CMC_PRO_API_KEY": KEY, "Accept": "application/json"}, timeout=30)
    ms = int((time.time() - t0) * 1000)
    if code == 0:
        return {"http": 0, "verdict": "network-error",
                "msg": (raw.decode("utf8", "ignore") or "unreachable")[:80],
                "ms": ms, "url": url, "body": None}
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    st = data.get("status", {}) or {}
    err_code, err_msg = st.get("error_code"), (st.get("error_message") or "")

    # The trap: 200 + error_code 500 "system is busy" means the PATH DOES NOT EXIST.
    if code == 200 and err_code in (500, "500"):
        verdict = "PATH-ABSENT"
    elif code == 200:
        verdict = "OK"
    elif code == 403:
        verdict = "PLAN-BLOCKED"
    elif code == 401:
        verdict = "BAD-KEY"
    elif code == 400:
        verdict = "bad-params"
    elif code == 429:
        verdict = "rate-limited"
    elif code == 404:
        verdict = "PATH-ABSENT"
    else:
        verdict = str(code)
    return {"http": code, "verdict": verdict, "msg": str(err_msg)[:80],
            "ms": ms, "url": url, "body": data}


def describe(node, depth=0, prefix=""):
    """Print the shape of a payload without dumping all of it."""
    pad = "  " * depth
    if isinstance(node, dict):
        for k, v in list(node.items())[:40]:
            if isinstance(v, (dict, list)):
                print(f"{pad}{prefix}{k}:")
                describe(v, depth + 1)
            else:
                print(f"{pad}{prefix}{k} = {repr(v)[:70]}")
    elif isinstance(node, list):
        print(f"{pad}[{len(node)} items]")
        if node:
            describe(node[0], depth + 1)


results = []
print(f"CMC key probe  {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 78)
for group, label, path, params in PROBES:
    r = call(path, params)
    r.update(group=group, label=label, path=path)
    results.append(r)
    mark = {"OK": "  OK  ", "PLAN-BLOCKED": " PLAN ", "PATH-ABSENT": " GONE ",
            "BAD-KEY": " KEY! "}.get(r["verdict"], "  ??  ")
    print(f"{mark}{group:<10}{label:<22}{str(r['http']):<5}{r['verdict']:<14}{r['msg']}")
    time.sleep(0.25)

print("=" * 78)

# --- control sanity -------------------------------------------------------
ctrl = [r for r in results if r["group"] == "control"]
if not all(c["verdict"] == "PATH-ABSENT" for c in ctrl):
    print("\n!! CONTROLS FAILED. A path that should not exist did not report absent.")
    print("!! Every verdict below is suspect. Do not act on this run.\n")

# --- tier -----------------------------------------------------------------
ki = next((r for r in results if r["label"] == "key info"), None)
tier = None
if ki and ki["verdict"] == "OK":
    plan = (ki["body"].get("data") or {}).get("plan", {}) or {}
    used = ((ki["body"].get("data") or {}).get("usage", {}) or {}).get("current_month", {})
    limit = plan.get("credit_limit_monthly")
    tier = TIERS.get(limit, f"unrecognised ({limit})")
    print(f"\nPLAN      credit_limit_monthly = {limit}  ->  {tier}")
    print(f"          rate_limit_minute    = {plan.get('rate_limit_minute')}")
    print(f"          credits used so far  = {(used or {}).get('credits_used')}")
    if limit == 15000:
        print("\n  *** YOUR HACKATHON UPGRADE HAS NOT LANDED. You are on the free Basic tier.")
        print("  *** Raise it on the DoraHacks Q&A tab TODAY - this takes days to resolve.")

# --- the decision ---------------------------------------------------------
mv = [r for r in results if r["label"].startswith("most visited")]
ok = [r for r in mv if r["verdict"] == "OK"]
print("\n" + "=" * 78)
if ok:
    print("GO.  trending/most-visited is callable. Attention data is available.\n")
    d = ok[0]["body"].get("data")
    n = len(d) if isinstance(d, list) else "?"
    print(f"Returned {n} records for time_period=24h. Shape of the first one:")
    print("-" * 78)
    describe(d[0] if isinstance(d, list) and d else d)
    print("-" * 78)
    print("\nDECIDE NOW, looking at the fields above:")
    print("  * Is there a view count / score / magnitude?  -> signal = attention level")
    print("  * Only ordering and rank?                     -> signal = rank velocity")
    print("  * How deep does the list go? (pass limit=200 to find the ceiling)")
else:
    print("NO-GO on the attention plan. most-visited is not callable:")
    for r in mv:
        print(f"   {r['http']} {r['verdict']} {r['msg']}")
    print("\nFall back to the positioning axis (/v5 derivatives) and escalate the tier.")

raw = OUT / f"probe-{time.strftime('%Y%m%dT%H%M%S')}.json"
raw.write_text(json.dumps(results, indent=2, default=str))
print(f"\nFull raw responses saved to {raw}")
print("Keep these. They are the 'visible evidence of a real API call' the submission asks for.")
