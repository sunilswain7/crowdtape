"""
The classifier.

Three axes, each reduced to a state, then combined into one reading. Thresholds are
constants at the top of this file rather than buried in the logic, because a heuristic
nobody can see is a heuristic nobody can argue with - and every one of these is a
judgement call that deserves arguing with.

Nothing here touches the network or a payload shape. It reads canonical records only,
so it is testable without a key, which is why the tests run on any machine and in CI.
"""
from __future__ import annotations
import dataclasses, statistics
from enum import Enum

from .normalize import CoinState

# --- thresholds. Visible on purpose. --------------------------------------------
PRICE_MOVE_PCT = 2.0        # |24h %| below this counts as going nowhere
ATTENTION_JUMP = 5          # places gained on the most-visited list to count as rising
TURNOVER_Z = 1.5            # fallback: z-score of volume/mcap against the universe
LIQ_INTENSITY_PCT = 0.0015  # 24h liquidations over market cap, above which positioning
                            # counts as stressed rather than quiet (0.15%)
LIQ_SKEW = 0.65             # share of liquidations on one side to call it lopsided
MIN_UNIVERSE = 20           # below this the cross-sectional z-scores are meaningless


class Price(str, Enum):
    UP = "up"; FLAT = "flat"; DOWN = "down"


class Attention(str, Enum):
    RISING = "rising"; STEADY = "steady"; UNKNOWN = "unknown"


class Leverage(str, Enum):
    LONGS_FLUSHING = "longs_flushing"
    SHORTS_SQUEEZED = "shorts_squeezed"
    QUIET = "quiet"
    UNKNOWN = "unknown"


class Reading(str, Enum):
    LOADED_SPRING = "loaded_spring"          # crowd arriving, price has not moved
    EXIT_LIQUIDITY = "exit_liquidity"        # crowd arriving late into a move
    QUIET_ACCUMULATION = "quiet_accumulation" # move with nobody watching
    CAPITULATION = "capitulation"            # crowd arriving into a flush
    NOTHING = "nothing"


@dataclasses.dataclass(frozen=True)
class Verdict:
    coin_id: int
    symbol: str
    at: str
    reading: Reading
    price: Price
    attention: Attention
    leverage: Leverage
    why: str                 # one line, human readable, shown in the UI verbatim
    confident: bool          # False when an axis was unavailable


def classify_price(s: CoinState) -> Price:
    if s.pct_24h is None:
        return Price.FLAT
    if s.pct_24h >= PRICE_MOVE_PCT:
        return Price.UP
    if s.pct_24h <= -PRICE_MOVE_PCT:
        return Price.DOWN
    return Price.FLAT


def classify_attention(s: CoinState, prev: CoinState | None,
                       turnover_z: float | None) -> Attention:
    """Prefers the real signal - movement up the most-visited list - and falls back to
    turnover only when the attention stream is unavailable. The fallback is a proxy for
    'unusual interest', not the same measurement, and callers mark it low confidence."""
    if s.attention_rank is not None:
        if prev is None or prev.attention_rank is None:
            return Attention.RISING      # appearing on the list at all is the event
        if prev.attention_rank - s.attention_rank >= ATTENTION_JUMP:
            return Attention.RISING
        return Attention.STEADY
    if turnover_z is not None:
        return Attention.RISING if turnover_z >= TURNOVER_Z else Attention.STEADY
    return Attention.UNKNOWN


def classify_leverage(s: CoinState) -> Leverage:
    total, share = s.liq_total_24h, s.long_share
    if total is None or not s.market_cap:
        return Leverage.UNKNOWN
    if total / s.market_cap < LIQ_INTENSITY_PCT:
        return Leverage.QUIET
    if share is None:
        return Leverage.UNKNOWN
    if share >= LIQ_SKEW:
        return Leverage.LONGS_FLUSHING
    if share <= 1 - LIQ_SKEW:
        return Leverage.SHORTS_SQUEEZED
    return Leverage.QUIET


def _read(p: Price, a: Attention, lev: Leverage) -> tuple[Reading, str]:
    if a is Attention.RISING and p is Price.FLAT:
        return Reading.LOADED_SPRING, "Lookups climbing while the price has gone nowhere."
    if a is Attention.RISING and p is Price.UP:
        if lev is Leverage.SHORTS_SQUEEZED:
            return Reading.EXIT_LIQUIDITY, "Crowd arriving into a move already squeezing shorts."
        return Reading.EXIT_LIQUIDITY, "Crowd arriving after the move, not before it."
    if a is Attention.RISING and p is Price.DOWN:
        return Reading.CAPITULATION, "Lookups spiking into a fall."
    if a is Attention.STEADY and p is Price.UP:
        return Reading.QUIET_ACCUMULATION, "Price climbing with no rise in lookups."
    return Reading.NOTHING, "Nothing separating this from the rest of the tape."


def classify(states: list[CoinState],
             previous: dict[int, CoinState] | None = None) -> list[Verdict]:
    """One snapshot's worth of assets, against the snapshot before it."""
    previous = previous or {}

    z_by_id: dict[int, float] = {}
    turnovers = [(s.coin_id, s.turnover) for s in states if s.turnover is not None]
    if len(turnovers) >= MIN_UNIVERSE:
        vals = [t for _, t in turnovers]
        mu = statistics.fmean(vals)
        sd = statistics.pstdev(vals)
        if sd > 0:
            z_by_id = {cid: (t - mu) / sd for cid, t in turnovers}

    out = []
    for s in states:
        prev = previous.get(s.coin_id)
        p = classify_price(s)
        a = classify_attention(s, prev, z_by_id.get(s.coin_id))
        lev = classify_leverage(s)
        reading, why = _read(p, a, lev)
        out.append(Verdict(
            coin_id=s.coin_id, symbol=s.symbol, at=s.at, reading=reading,
            price=p, attention=a, leverage=lev, why=why,
            # An attention reading derived from turnover is a proxy, and a missing
            # leverage axis is a missing axis. Neither is dressed up as certainty.
            confident=(s.attention_rank is not None and lev is not Leverage.UNKNOWN),
        ))
    return out
