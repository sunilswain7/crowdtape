"""
Raw CoinMarketCap payloads -> canonical records.

Every field name CoinMarketCap chose lives in this file and nowhere else. The engine
downstream reads only the canonical shape, so when a payload turns out to differ from
what was assumed, exactly one function changes and the logic and its tests are untouched.

`liquidations` was corrected on 19 Sep 2026 from an observed response - see
docs/payload-shapes.md. Two formats are read, because the recorder's own thinning changed
on that date and the snapshots taken before it are still valid data:
`{"rows": [...]}` (current) and `{"cryptocurrencies": [...]}` (raw, as first recorded).

`most_visited` was observed on 22 Sep once the plan allowed it. **It carries no
magnitude** - no view count, no traffic score; `cmc_rank` in that payload is the
market-cap rank. Attention is therefore the POSITION in the returned list and nothing
else, stored by the recorder as `a`.

The 24h stream also returns a full quote, which matters: the most-visited asset on
CoinMarketCap at the time of writing was EDEL, at market-cap rank 683. Assets like that
are the entire point of the signal and would be invisible in a top-200 universe, so the
universe is the **union** of the market-cap listing and the attention list.

    python3 -m engine.normalize data/2026-09-19.jsonl

prints what was matched and what was dropped, which is how the rest gets corrected.
"""
from __future__ import annotations
import dataclasses, json, sys, pathlib
from typing import Any, Iterable


@dataclasses.dataclass(frozen=True)
class CoinState:
    """One asset at one instant. The only shape the engine knows about."""
    at: str
    coin_id: int
    symbol: str
    price: float | None = None
    market_cap: float | None = None
    volume_24h: float | None = None
    rank: int | None = None
    pct_1h: float | None = None
    pct_24h: float | None = None
    pct_7d: float | None = None
    # attention: 1 = most looked at. None means either "not on the list" or "the stream
    # was unavailable", and the difference matters enormously - absent from a list you
    # could see is evidence of low interest, absent because you are blind is not.
    attention_rank: int | None = None
    attention_available: bool = False
    # Position on the longer horizons. High 24h attention with no 7d or 30d presence is
    # brand-new interest; present on all three is a standing crowd.
    #
    # `None` on a rank is ambiguous on its own - it means either "absent from that list"
    # or "that list was never read" - so the flag says which. Without it, a snapshot
    # taken before the 30d stream existed would read as every asset being brand new.
    attention_rank_7d: int | None = None
    attention_rank_30d: int | None = None
    attention_30d_available: bool = False
    # None means CoinMarketCap did not return tags on this snapshot, which is not the
    # same as "not a stablecoin" and must not be treated as it.
    is_stablecoin: bool | None = None
    # Distinct wallets holding the token, and the change since the previous holder pass.
    # This is the crowd axis: an actual count of holders rather than a proxy for interest.
    wallet_count: int | None = None
    wallet_growth: float | None = None
    # positioning, in USD. 1h is the sharper read - at a ten-minute snapshot interval a
    # 24h window is mostly yesterday - but both are kept because 24h gives the context
    # that says whether an hour was unusual.
    liq_long_1h: float | None = None
    liq_short_1h: float | None = None
    liq_long_24h: float | None = None
    liq_short_24h: float | None = None

    @property
    def turnover(self) -> float | None:
        """Volume against size. The attention proxy that needs no attention endpoint -
        it is what the engine falls back to while the Startup tier is pending."""
        if not self.market_cap or self.volume_24h is None:
            return None
        return self.volume_24h / self.market_cap

    @property
    def liq_total_24h(self) -> float | None:
        if self.liq_long_24h is None and self.liq_short_24h is None:
            return None
        return (self.liq_long_24h or 0.0) + (self.liq_short_24h or 0.0)

    @property
    def long_share(self) -> float | None:
        """Of what was liquidated, how much was longs. >0.5 means longs got carried out."""
        t = self.liq_total_24h
        if not t:
            return None
        return (self.liq_long_24h or 0.0) / t


def _num(d: dict, *names: str) -> float | None:
    """First of `names` present and numeric. CMC abbreviates inconsistently across
    endpoint families, so candidates are listed rather than assumed."""
    for n in names:
        v = d.get(n)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _ident(d: dict) -> tuple[int | None, str | None]:
    cid = d.get("id") or d.get("cryptoId") or d.get("crypto_id")
    sym = d.get("symbol") or d.get("s") or d.get("code")
    try:
        cid = int(cid) if cid is not None else None
    except (TypeError, ValueError):
        cid = None
    return cid, (str(sym).upper() if sym else None)


def from_snapshot(snap: dict,
                  holders: "HolderSeries | None" = None) -> tuple[list[CoinState], dict[str, str]]:
    """One snapshot line -> (canonical records, notes about what could not be read)."""
    at = snap.get("at", "")
    streams = snap.get("streams", {}) or {}
    notes: dict[str, str] = {}

    def data(name: str) -> Any:
        s = streams.get(name) or {}
        if "error" in s:
            notes[name] = s["error"]
            return None
        return s.get("data")

    # --- price. Observed shape: the recorder already thins this one. ---
    by_id: dict[int, dict] = {}
    for c in (data("listings") or []):
        cid = c.get("id")
        if cid is None:
            continue
        by_id[int(cid)] = {
            "symbol": (c.get("s") or "").upper(),
            "price": c.get("p"), "market_cap": c.get("mc"), "volume_24h": c.get("v"),
            "rank": c.get("r"), "st": c.get("st"), "pct_1h": c.get("c1"),
            "pct_24h": c.get("c24"), "pct_7d": c.get("c7"),
        }

    # --- attention. UNVERIFIED shape. Rank is position in the returned list; the
    #     recorder preserves whole records so a magnitude field, if one exists, is
    #     not thrown away before it has been seen.
    mv = data("most_visited_24h")
    attention_available = isinstance(mv, list) and bool(mv)
    att: dict[int, int] = {}
    unlisted: dict[int, dict] = {}
    if isinstance(mv, list):
        for row in mv:
            cid = row.get("id")
            if cid is None:
                continue
            cid = int(cid)
            att[cid] = int(row["a"])
            # Rows carrying a symbol are the ones `listings` did not cover: assets with
            # real attention and too little market cap for the top 200.
            if "s" in row:
                unlisted[cid] = row
        if mv and not att:
            notes["most_visited_24h"] = "records present but no id field matched"

    def horizon(name: str) -> dict[int, int]:
        rows = data(name)
        return {int(r["id"]): int(r["a"]) for r in rows
                if isinstance(r, dict) and r.get("id") is not None} \
            if isinstance(rows, list) else {}

    att7, att30 = horizon("most_visited_7d"), horizon("most_visited_30d")
    att30_available = bool(att30)

    # The universe is the union: market-cap ranked assets plus attention outliers.
    for cid, row in unlisted.items():
        by_id.setdefault(cid, {
            "symbol": (row.get("s") or "").upper(), "price": row.get("p"),
            "market_cap": row.get("mc"), "volume_24h": row.get("v"),
            "rank": row.get("r"), "st": row.get("st"), "pct_1h": row.get("c1"),
            "pct_24h": row.get("c24"), "pct_7d": row.get("c7"),
        })

    # --- positioning. UNVERIFIED shape. ---
    liq: dict[int, tuple] = {}
    lq = data("liquidations") or {}
    if isinstance(lq, dict) and "rows" in lq:
        for row in lq["rows"]:
            cid = row.get("id")
            if cid is not None:
                liq[int(cid)] = (row.get("l1"), row.get("s1"),
                                 row.get("l24"), row.get("s24"))
    elif isinstance(lq, dict) and "cryptocurrencies" in lq:
        # raw shape, as recorded before the thinning was corrected
        for c in lq["cryptocurrencies"] or []:
            cid = c.get("crypto_id")          # the asset; the crypto_id inside
            if cid is None:                   # `quotes` is the convert currency
                continue
            q = (c.get("quotes") or [{}])[0]
            liq[int(cid)] = (q.get("long_liquidations_1h"), q.get("short_liquidations_1h"),
                             q.get("long_liquidations_24h"), q.get("short_liquidations_24h"))
    elif lq:
        notes["liquidations"] = f"unrecognised shape: {list(lq)[:4]}"

    wallets = holders.at(at) if holders else {}

    out = []
    for cid, m in by_id.items():
        l1, s1, l24, s24 = liq.get(cid, (None, None, None, None))
        wc, wg = wallets.get(cid, (None, None))
        out.append(CoinState(at=at, coin_id=cid, symbol=m["symbol"],
                             price=m["price"], market_cap=m["market_cap"],
                             volume_24h=m["volume_24h"], rank=m["rank"],
                             pct_1h=m["pct_1h"], pct_24h=m["pct_24h"], pct_7d=m["pct_7d"],
                             attention_rank=att.get(cid),
                             attention_available=attention_available,
                             attention_rank_7d=att7.get(cid),
                             attention_rank_30d=att30.get(cid),
                             attention_30d_available=att30_available,
                             is_stablecoin=m["st"],
                             wallet_count=wc, wallet_growth=wg,
                             liq_long_1h=l1, liq_short_1h=s1,
                             liq_long_24h=l24, liq_short_24h=s24))
    return out, notes


class HolderSeries:
    """Wallet counts over time, and the growth between consecutive passes.

    Counts are recorded every three hours while snapshots are every ten minutes, so a
    snapshot is matched to the most recent pass at or before it. Growth is measured
    against the pass before that one - never against a partial or future reading, which
    would leak information backwards into a signal the scorecard then grades.
    """

    def __init__(self, passes: list[tuple[str, dict[int, int]]]):
        self.passes = sorted(passes, key=lambda p: p[0])

    @classmethod
    def load(cls, data_dir: str | pathlib.Path) -> "HolderSeries":
        passes = []
        for f in sorted(pathlib.Path(data_dir).glob("holders-*.jsonl")):
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                counts = {int(h["id"]): int(h["n"])
                          for h in rec.get("holders", []) if h.get("n")}
                if counts:
                    passes.append((rec["at"], counts))
        return cls(passes)

    def _index_at(self, at: str) -> int:
        lo = -1
        for i, (t, _) in enumerate(self.passes):
            if t <= at:
                lo = i
            else:
                break
        return lo

    def at(self, at: str) -> dict[int, tuple[int, float | None]]:
        """{coin_id: (count, growth_since_previous_pass)} as of this instant."""
        i = self._index_at(at)
        if i < 0:
            return {}
        _, now = self.passes[i]
        prev = self.passes[i - 1][1] if i > 0 else {}
        out = {}
        for cid, n in now.items():
            was = prev.get(cid)
            out[cid] = (n, (n - was) / was if was else None)
        return out


def load(path: str | pathlib.Path,
         holders: HolderSeries | None = None) -> Iterable[tuple[list[CoinState], dict]]:
    for line in pathlib.Path(path).read_text().splitlines():
        if line.strip():
            yield from_snapshot(json.loads(line), holders)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 -m engine.normalize data/YYYY-MM-DD.jsonl")
    n = 0
    seen_notes: dict[str, str] = {}
    cover = {"attention": 0, "liquidations": 0}
    for states, notes in load(sys.argv[1]):
        n += 1
        seen_notes.update(notes)
        cover["attention"] += sum(1 for s in states if s.attention_rank is not None)
        cover["liquidations"] += sum(1 for s in states if s.liq_total_24h is not None)
        last = states
    print(f"{n} snapshots, {len(last)} assets in the most recent")
    print(f"attention covered   : {cover['attention']} asset-observations")
    print(f"liquidations covered: {cover['liquidations']} asset-observations")
    if seen_notes:
        print("\ncould not read:")
        for k, v in seen_notes.items():
            print(f"  {k}: {v}")
