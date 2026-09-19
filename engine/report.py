"""
Turns the recorded snapshots into the three files the site reads.

The site is static. It holds no key, calls no API and has no backend: this runs inside
the recorder's own job, writes JSON next to the data, and the page fetches that. Which
also means the published board is exactly reproducible from the repository by anyone who
runs this command - there is no server holding a different answer.

    python3 -m engine.report

Writes site/data/{latest,events,scorecard}.json
"""
from __future__ import annotations
import collections, datetime, json, pathlib, statistics, sys

from .normalize import load, CoinState
from .signal import classify, Reading
from .events import HORIZONS_H, detect, score, scorecard

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data"
GRADE_TOLERANCE = 0.25      # a horizon is gradeable if a snapshot sits within ±25% of it


def _ts(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def build():
    files = sorted((ROOT / "data").glob("*.jsonl"))
    if not files:
        sys.exit("no data recorded yet")

    snapshots: list[tuple[str, list[CoinState], dict]] = []
    for f in files:
        for states, notes in load(f):
            if states:
                snapshots.append((states[0].at, states, notes))
    snapshots.sort(key=lambda x: x[0])

    # classify every snapshot against the one before it
    verdicts_by_ts: dict[str, list] = {}
    prices_by_ts: dict[str, dict[int, float]] = {}
    history: dict[int, list] = collections.defaultdict(list)
    prev: dict[int, CoinState] = {}
    for at, states, _ in snapshots:
        vs = classify(states, prev)
        verdicts_by_ts[at] = vs
        prices_by_ts[at] = {s.coin_id: s.price for s in states if s.price}
        for v in vs:
            history[v.coin_id].append((v, prices_by_ts[at].get(v.coin_id)))
        prev = {s.coin_id: s for s in states}

    events = [e for h in history.values() for e in detect(h)]
    events.sort(key=lambda e: e.opened_at, reverse=True)

    # --- grade what is old enough to grade ----------------------------------
    ordered_ts = sorted(prices_by_ts)
    scores = []
    for ev in events:
        opened = _ts(ev.opened_at)
        for h in HORIZONS_H:
            target = opened + datetime.timedelta(hours=h)
            window = datetime.timedelta(hours=h * GRADE_TOLERANCE)
            best = min((t for t in ordered_ts if abs(_ts(t) - target) <= window),
                       key=lambda t: abs(_ts(t) - target), default=None)
            if best is None:
                continue                      # not yet, or the recorder had a gap
            then, at_open = prices_by_ts[best], prices_by_ts.get(ev.opened_at, {})
            price_then = then.get(ev.coin_id)
            if not price_then:
                continue
            universe = [(then[c] - at_open[c]) / at_open[c]
                        for c in at_open if c in then and at_open[c]]
            s = score(ev, h, price_then, universe)
            if s:
                scores.append(s)

    OUT.mkdir(parents=True, exist_ok=True)
    at, states, notes = snapshots[-1][0], snapshots[-1][1], snapshots[-1][2]
    vs = verdicts_by_ts[at]
    by_id = {s.coin_id: s for s in states}
    moves = [s.pct_24h for s in states if s.pct_24h is not None and not s.is_stablecoin]

    rows = []
    for v in sorted(vs, key=lambda v: (v.reading is Reading.NOTHING,
                                       by_id[v.coin_id].rank or 9999)):
        s = by_id[v.coin_id]
        rows.append({
            "id": v.coin_id, "symbol": v.symbol, "rank": s.rank, "price": s.price,
            "pct_24h": s.pct_24h, "market_cap": s.market_cap, "volume_24h": s.volume_24h,
            "reading": v.reading.value, "price_state": v.price.value,
            "attention": v.attention.value, "leverage": v.leverage.value,
            "why": v.why, "confident": v.confident,
            "attention_rank": s.attention_rank,
            "liq_long_24h": s.liq_long_24h, "liq_short_24h": s.liq_short_24h,
        })

    (OUT / "latest.json").write_text(json.dumps({
        "at": at,
        "snapshots_recorded": len(snapshots),
        "first_recorded": snapshots[0][0],
        "universe": len(states),
        "median_move_24h": statistics.median(moves) if moves else None,
        # Stated on the page, not hidden in a footnote: every reading is weaker while
        # this is false, and the page says so rather than implying a signal it lacks.
        "attention_available": any(s.attention_available for s in states),
        "unavailable": notes,
        "rows": rows,
    }, separators=(",", ":"), default=str))

    scored_by_event = collections.defaultdict(dict)
    for s in scores:
        scored_by_event[(s.event.coin_id, s.event.opened_at)][s.horizon_h] = {
            "excess": s.excess_return, "coin": s.coin_return,
            "universe": s.universe_return, "hit": s.hit}
    (OUT / "events.json").write_text(json.dumps([{
        "symbol": e.symbol, "id": e.coin_id, "reading": e.reading.value,
        "opened_at": e.opened_at, "price_at_open": e.price_at_open,
        "why": e.why, "confident": e.confident,
        "scores": scored_by_event.get((e.coin_id, e.opened_at), {}),
    } for e in events[:500]], separators=(",", ":"), default=str))

    # --- per-asset series for the charts ------------------------------------
    # Only the assets currently carrying a reading, and only the recent window: the
    # whole universe at full history would be megabytes the page has no use for.
    flagged = [r["id"] for r in rows if r["reading"] != "nothing"][:40]
    recent = [t for t in ordered_ts][-500:]

    # The market's own path, as the median asset. Indexing both this and each asset to
    # 100 at the start of the window puts them on ONE axis honestly - which is the only
    # legitimate way to plot "the coin" against "the market" without inventing a
    # correlation out of two arbitrary scales.
    base = prices_by_ts[recent[0]] if recent else {}
    market = []
    for t in recent:
        rel = [prices_by_ts[t][c] / base[c] for c in base
               if c in prices_by_ts[t] and base[c]]
        if rel:
            market.append({"t": t, "i": 100 * statistics.median(rel)})

    series = {"__market__": market}
    for cid in flagged:
        pts = []
        for t in recent:
            st = next((x for x in verdicts_by_ts[t] if x.coin_id == cid), None)
            if st is None:
                continue
            price = prices_by_ts[t].get(cid)
            if price is None:
                continue
            pts.append({"t": t, "p": price, "r": st.reading.value,
                        "i": 100 * price / base[cid] if base.get(cid) else None})
        if len(pts) >= 2:
            series[str(cid)] = pts
    (OUT / "series.json").write_text(json.dumps(series, separators=(",", ":"), default=str))

    cards = scorecard(scores)
    (OUT / "scorecard.json").write_text(json.dumps({
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "events_total": len(events),
        "events_graded": len({(s.event.coin_id, s.event.opened_at) for s in scores
                              if s.hit is not None}),
        "cards": [{"reading": c.reading.value, "horizon_h": c.horizon_h, "n": c.n,
                   "graded": c.graded, "hits": c.hits, "hit_rate": c.hit_rate,
                   "mean_excess": c.mean_excess} for c in cards],
    }, separators=(",", ":"), default=str))

    print(f"{len(snapshots)} snapshots -> {len(events)} events, "
          f"{len(scores)} graded readings, {len(rows)} rows")
    for c in cards:
        print("  ", c)


if __name__ == "__main__":
    build()
