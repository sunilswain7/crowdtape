"""
The classifier.

Three axes, each reduced to a state, then combined into one reading. Thresholds are
constants at the top of this file rather than buried in the logic, because a heuristic
nobody can see is a heuristic nobody can argue with - and every one of these is a
judgement call that deserves arguing with.

Every axis is **cross-sectional**: an asset is read against the rest of the universe at
that same instant, never against a fixed number. The first run against real data made the
reason obvious - on a day the total market cap rose 4.2%, an absolute "up more than 2%"
test called 126 of 200 assets `quiet_accumulation`. That is not a signal, it is beta with
a label on it. Price is now judged on its excess over the universe median, and liquidation
stress on its rank within the universe, so both tighten automatically when the whole tape
is moving and loosen when it is still.

Nothing here touches the network or a payload shape. It reads canonical records only,
so it is testable without a key, which is why the tests run on any machine and in CI.
"""
from __future__ import annotations
import dataclasses, statistics
from enum import Enum

from .normalize import CoinState

# --- thresholds. Visible on purpose. --------------------------------------------
PRICE_EXCESS_PCT = 2.0      # 24h move minus the universe median, in points
ATTENTION_JUMP = 5          # places gained on the most-visited list to count as rising
TURNOVER_Z = 1.5            # fallback: z-score of volume/mcap to count as rising
TURNOVER_Z_QUIET = -0.5     # fallback: below this, interest is genuinely below average
LIQ_STRESS_PCTILE = 0.75    # liquidations over market cap, ranked; above this quartile
                            # positioning counts as stressed rather than quiet
LIQ_SKEW = 0.65             # share of liquidations on one side to call it lopsided
MIN_UNIVERSE = 20           # below this the cross-sectional measures are meaningless


class Price(str, Enum):
    UP = "up"; FLAT = "flat"; DOWN = "down"


class Attention(str, Enum):
    RISING = "rising"      # climbing the most-visited list, or unusually high turnover
    STEADY = "steady"      # on the list and not moving much
    QUIET = "quiet"        # measurably little interest - not merely unmeasured
    UNKNOWN = "unknown"    # no way to tell


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


def classify_price(s: CoinState, universe_median_pct: float = 0.0) -> Price:
    """Judged on the move net of the market's own. A coin up 3% on a day the median coin
    is up 4% has not gone up in any sense that matters - it has gone down relative to the
    alternative of owning anything else."""
    if s.pct_24h is None:
        return Price.FLAT
    excess = s.pct_24h - universe_median_pct
    if excess >= PRICE_EXCESS_PCT:
        return Price.UP
    if excess <= -PRICE_EXCESS_PCT:
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
    if s.attention_available:
        # The list was readable and this asset is not on it. That is a measurement of
        # low interest, and it is the cleanest `quiet` this engine ever gets.
        return Attention.QUIET
    if turnover_z is not None:
        if turnover_z >= TURNOVER_Z:
            return Attention.RISING
        if turnover_z <= TURNOVER_Z_QUIET:
            return Attention.QUIET
        return Attention.STEADY          # ordinary interest is not an absence of it
    return Attention.UNKNOWN


def classify_leverage(s: CoinState, stress_cutoff: float | None = None) -> Leverage:
    """`stress_cutoff` is the universe's own upper-quartile liquidation intensity. A
    fixed cutoff mislabels a quiet market as stressed and a violent one as calm."""
    total, share = s.liq_total_24h, s.long_share
    if total is None or not s.market_cap:
        return Leverage.UNKNOWN
    if stress_cutoff is None or total / s.market_cap < stress_cutoff:
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
    if a is Attention.QUIET and p is Price.UP:
        return Reading.QUIET_ACCUMULATION, "Outperforming while interest sits below average."
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

    # The two cross-sectional reference points, recomputed every snapshot.
    moves = [s.pct_24h for s in states
             if s.pct_24h is not None and not s.is_stablecoin]
    median_move = statistics.median(moves) if len(moves) >= MIN_UNIVERSE else 0.0

    intensities = sorted(s.liq_total_24h / s.market_cap for s in states
                         if s.market_cap and s.liq_total_24h)
    stress_cutoff = None
    if len(intensities) >= MIN_UNIVERSE:
        stress_cutoff = intensities[int(len(intensities) * LIQ_STRESS_PCTILE)]

    out = []
    for s in states:
        prev = previous.get(s.coin_id)
        if s.is_stablecoin:
            # An asset designed not to move cannot be read on a cross-sectional price
            # measure: on any day the market rises, every peg "underperforms" it. Judging
            # a stablecoin needs a depeg test, which is a different instrument entirely.
            out.append(Verdict(coin_id=s.coin_id, symbol=s.symbol, at=s.at,
                               reading=Reading.NOTHING, price=Price.FLAT,
                               attention=Attention.UNKNOWN, leverage=Leverage.UNKNOWN,
                               why="Stablecoin - not read on a relative price measure.",
                               confident=False))
            continue
        p = classify_price(s, median_move)
        a = classify_attention(s, prev, z_by_id.get(s.coin_id))
        lev = classify_leverage(s, stress_cutoff)
        reading, why = _read(p, a, lev)
        out.append(Verdict(
            coin_id=s.coin_id, symbol=s.symbol, at=s.at, reading=reading,
            price=p, attention=a, leverage=lev, why=why,
            # An attention reading derived from turnover is a proxy, and a missing
            # leverage axis is a missing axis. Neither is dressed up as certainty.
            confident=(s.attention_rank is not None and lev is not Leverage.UNKNOWN),
        ))
    return out
