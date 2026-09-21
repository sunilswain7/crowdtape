#!/usr/bin/env python3
"""
Crowdtape on Telegram.

The bot never calls CoinMarketCap. It reads the JSON the recorder already publishes to
GitHub Pages, which means it holds no API key, spends no credits, and cannot drift from
the board - if the site says a thing, so does the bot, because it is the same file.

It answers where people already are. The dashboard is a page a judge opens once; this is
the same readings in the place someone actually checks the market from, and every answer
carries the same honesty the site does: an unconfirmed reading says so, and a rejected
one says that too.

Stdlib only. Long-polls, so it needs no public URL and no webhook.

    TELEGRAM_BOT_TOKEN=... python3 bot/telegram.py
"""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, sys, time, urllib.parse, urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    sys.exit("TELEGRAM_BOT_TOKEN not set")

API = f"https://api.telegram.org/bot{TOKEN}"
SITE = os.environ.get("CROWDTAPE_SITE", "https://sunilswain7.github.io/crowdtape")
ROOT = pathlib.Path(__file__).resolve().parent.parent
USAGE = pathlib.Path(os.environ.get("CROWDTAPE_DATA_DIR") or ROOT / "data") / "bot-usage.jsonl"
DURATION = int(os.environ.get("BOT_DURATION_S", str(5 * 3600 + 40 * 60)))
CACHE_TTL = 120
COMMIT_EVERY_S = int(os.environ.get("BOT_COMMIT_EVERY_S", "600"))

READING = {
    "loaded_spring":      "🔵 Loaded spring",
    "exit_liquidity":     "🟠 Exit liquidity",
    "quiet_accumulation": "🟢 Quiet accumulation",
    "capitulation":       "⚪ Capitulation",
    "nothing":            "No reading",
}
LEVERAGE = {"longs_flushing": "longs flushing", "shorts_squeezed": "shorts squeezed",
            "quiet": "quiet", "unknown": "no data"}
VERDICT_MARK = {"supported": "✅", "rejected": "❌", "no edge": "➖",
                "not graded": "·", "too early": "⏳"}

_cache: dict[str, tuple[float, object]] = {}


def site(name: str):
    """Fetch a published file, briefly cached. The bot is a reader, never a writer."""
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    req = urllib.request.Request(f"{SITE}/data/{name}?t={int(time.time())}",
                                 headers={"User-Agent": "crowdtape-bot"})
    data = json.loads(urllib.request.urlopen(req, timeout=25).read())
    _cache[name] = (time.time(), data)
    return data


def tg(method: str, **params):
    body = urllib.parse.urlencode(
        {k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
         for k, v in params.items() if v is not None}).encode()
    req = urllib.request.Request(f"{API}/{method}", data=body)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=70).read())
    except Exception as e:
        print(f"  tg {method} failed: {str(e)[:120]}", flush=True)
        return {}


def say(chat: int, text: str):
    tg("sendMessage", chat_id=chat, text=text, parse_mode="HTML",
       disable_web_page_preview=True)


def log(chat: int, command: str):
    """Counts, never identities. The chat id is hashed before it touches disk, so the
    submission can honestly report unique users without publishing who they are."""
    who = hashlib.sha256(f"crowdtape:{chat}".encode()).hexdigest()[:12]
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE.open("a") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "user": who, "command": command}) + "\n")


def commit_usage():
    """Push the usage counts as they accrue.

    The workflow's concurrency rule cancels this job every three hours, and a cancelled
    job never reaches its post-run steps - so committing only at the end would throw away
    every message served in that window. Usage evidence is the one thing here that cannot
    be regenerated from anything, so it is pushed as it happens.
    """
    if not USAGE.exists():
        return
    for args in (["git", "add", str(USAGE)],
                 ["git", "commit", "-m",
                  f"bot usage {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}"],
                 ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                 ["git", "push", "origin", "HEAD:main"]):
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        if args[1] == "commit" and r.returncode != 0:
            return          # nothing new staged
    print("  usage pushed", flush=True)


def pct(v, dp=2):
    return "—" if v is None else f"{v:+.{dp}f}%"


def money(v):
    if v is None:
        return "—"
    for cut, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(v) >= cut:
            return f"${v/cut:.2f}{suf}"
    return f"${v:,.0f}"


def price(v):
    return "—" if v is None else (f"${v:,.2f}" if v >= 1 else f"${v:.6g}")


# --- commands ---------------------------------------------------------------

def cmd_start(chat, _):
    say(chat,
        "<b>Crowdtape</b>\n"
        "<i>The tape is what happened. The crowd is what happens next.</i>\n\n"
        "CoinMarketCap keeps no history of who is looking at what, or of how leverage "
        "builds. This records both every ten minutes and reads them against price.\n\n"
        "<b>/board</b> — what is carrying a reading right now\n"
        "<b>/coin BTC</b> — one asset in full\n"
        "<b>/score</b> — whether these readings actually work\n"
        "<b>/why</b> — what the four readings mean\n\n"
        "Start with <b>/score</b>. It is the only one that tells you which readings to "
        "ignore.\n\n<i>Not investment advice.</i>")


def cmd_why(chat, _):
    say(chat,
        "<b>What the readings mean</b>\n\n"
        "Every asset is judged <i>against the rest of the market at that instant</i>, "
        "never against zero — on a day everything rises 4%, rising 3% is falling behind.\n\n"
        f"{READING['loaded_spring']}\nCrowd arriving while the price still tracks the "
        "market. Something building.\n\n"
        f"{READING['exit_liquidity']}\nCrowd arriving <i>after</i> the move. You may be "
        "who they are selling to.\n\n"
        f"{READING['quiet_accumulation']}\nOutperforming while interest sits below "
        "average. Moving without a crowd.\n\n"
        f"{READING['capitulation']}\nInterest spiking while it falls behind. Never "
        "graded — it claims no direction.\n\n"
        "The crowd is measured as <b>wallet growth</b>: how fast the number of distinct "
        "holders changes. Where that is unavailable it falls back to turnover, and the "
        "reading is marked <i>unconfirmed</i>.")


def cmd_board(chat, _):
    d = site("latest.json")
    rows = [r for r in d["rows"] if r["reading"] != "nothing"]
    order = ["loaded_spring", "exit_liquidity", "capitulation", "quiet_accumulation"]
    rows.sort(key=lambda r: (order.index(r["reading"]), r["rank"] or 9999))
    if not rows:
        return say(chat, "Nothing is carrying a reading right now. That is a real "
                         "answer, not a missing one.")
    out = [f"<b>The board</b> · {d['at'][:16].replace('T', ' ')} UTC",
           f"<i>{len(rows)} of {d['universe']} assets · median 24h "
           f"{pct(d['median_move_24h'])}</i>", ""]
    shown = 0
    for r in rows:
        if shown >= 18:
            out.append(f"\n<i>…and {len(rows) - shown} more. /coin SYMBOL for any of them.</i>")
            break
        excess = None if r["pct_24h"] is None else r["pct_24h"] - d["median_move_24h"]
        mark = "" if r["confident"] else " <i>·unconfirmed</i>"
        out.append(f"{READING[r['reading']]}  <b>{r['symbol']}</b>  "
                   f"{pct(r['pct_24h'],1)} ({pct(excess,1)} vs mkt){mark}")
        shown += 1
    if not d["attention_available"]:
        out.append("\n<i>CoinMarketCap's most-visited feed is not on this API plan, so "
                   "the crowd axis uses wallet growth where available.</i>")
    say(chat, "\n".join(out))


def cmd_coin(chat, args):
    if not args:
        return say(chat, "Give me a symbol: <b>/coin BTC</b>")
    sym = args[0].upper().lstrip("$")
    d = site("latest.json")
    r = next((x for x in d["rows"] if x["symbol"] == sym), None)
    if not r:
        return say(chat, f"<b>{sym}</b> is not in the top {d['universe']} by market cap, "
                         f"which is all this records.")
    excess = None if r["pct_24h"] is None else r["pct_24h"] - d["median_move_24h"]
    head = f"<b>{r['symbol']}</b> · rank {r['rank']}"
    out = [head, "",
           f"Price       {price(r['price'])}",
           f"24h         {pct(r['pct_24h'])}",
           f"vs market   <b>{pct(excess)}</b>",
           f"Market cap  {money(r['market_cap'])}", "",
           f"<b>{READING[r['reading']]}</b>",
           f"<i>{r['why']}</i>"]
    if r["reading"] == "nothing":
        out[-2] = "<b>No reading</b>"
    if r.get("wallet_count"):
        out.append(f"\nWallets     {r['wallet_count']:,}"
                   + (f"  ({r['wallet_growth']*100:+.3f}% since last pass)"
                      if r.get("wallet_growth") is not None else ""))
    if r["leverage"] != "unknown":
        out.append(f"Leverage    {LEVERAGE[r['leverage']]}")
    if not r["confident"]:
        out.append("\n<i>Unconfirmed: no wallet data for this asset, so the crowd axis "
                   "is turnover standing in for it.</i>")
    sc = site("scorecard.json").get("verdicts", {}).get(r["reading"])
    if sc and sc["verdict"] in ("rejected", "no edge"):
        out.append(f"\n⚠️ <b>This reading's record is '{sc['verdict']}'.</b> {sc['why']}")
    say(chat, "\n".join(out))


def cmd_score(chat, _):
    d = site("scorecard.json")
    out = ["<b>Does any of this work?</b>",
           f"<i>{d['events_total']} readings issued · {d['events_graded']} old enough "
           f"to grade</i>", "",
           "Each is scored on <b>excess return over the market median</b> — beating zero "
           "in a rising market is not skill. Misses included.", ""]
    for key in ("loaded_spring", "exit_liquidity", "quiet_accumulation", "capitulation"):
        v = (d.get("verdicts") or {}).get(key)
        if not v:
            continue
        out.append(f"{VERDICT_MARK.get(v['verdict'],'·')} <b>{READING[key]}</b> — "
                   f"{v['verdict'].upper()}\n<i>{v['why']}</i>\n")
    out.append("Full table: " + SITE)
    say(chat, "\n".join(out))


COMMANDS = {"start": cmd_start, "help": cmd_start, "board": cmd_board,
            "coin": cmd_coin, "c": cmd_coin, "score": cmd_score,
            "scorecard": cmd_score, "why": cmd_why}


def handle(msg):
    chat = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat or not text.startswith("/"):
        return
    parts = text.split()
    name = parts[0][1:].split("@")[0].lower()
    fn = COMMANDS.get(name)
    log(chat, name if fn else "unknown")
    if not fn:
        return say(chat, "I know /board, /coin, /score and /why.")
    try:
        fn(chat, parts[1:])
    except Exception as e:
        print(f"  {name} failed: {type(e).__name__}: {e}", flush=True)
        say(chat, "That broke on my side. The board is still at " + SITE)


def main():
    me = tg("getMe").get("result", {})
    print(f"crowdtape bot up as @{me.get('username','?')}, reading {SITE}", flush=True)
    tg("setMyCommands", commands=[
        {"command": "board", "description": "What is carrying a reading right now"},
        {"command": "coin", "description": "One asset in full — /coin BTC"},
        {"command": "score", "description": "Whether these readings actually work"},
        {"command": "why", "description": "What the four readings mean"},
    ])
    started, offset, served = time.time(), None, 0
    last_commit, pending = time.time(), 0
    while time.time() - started < DURATION:
        r = tg("getUpdates", offset=offset, timeout=50,
               allowed_updates=["message"])
        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            if "message" in upd:
                handle(upd["message"])
                served += 1
                pending += 1
                print(f"  served {served}", flush=True)
        if pending and time.time() - last_commit > COMMIT_EVERY_S:
            commit_usage()
            last_commit, pending = time.time(), 0
    if pending:
        commit_usage()
    print(f"done: {served} messages in {(time.time()-started)/60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
