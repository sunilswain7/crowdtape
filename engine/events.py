"""
Events and the scorecard.

A reading on its own is a claim. This turns readings into dated, immutable events and
then grades them against what the price actually did, so the claim becomes checkable.

Two choices here are worth defending:

**Excess return, not raw return.** An event is scored against the median forward return
of the universe at the same instant, not against zero. A "loaded spring" that gained 5%
on a day the whole market gained 6% did not find anything - it underperformed a coin
picked at random. Raw returns would flatter every reading in a rising market and damn
every reading in a falling one, which is how a scorecard becomes a marketing asset
instead of a measurement.

**Events debounce.** A reading has to hold for MIN_DWELL consecutive snapshots before it
opens an event. Without it, an asset sitting on a threshold flaps between two readings
every few minutes and manufactures dozens of events out of one situation.
"""
from __future__ import annotations
import dataclasses, datetime, statistics
from .signal import Reading, Verdict

MIN_DWELL = 2                       # consecutive snapshots a reading must hold
HORIZONS_H = (4, 24, 72)            # hours after the open at which an event is graded

# What each reading is actually predicting, as a sign on the excess return. A reading
# that predicts nothing in particular is not scored, rather than being given a direction
# that makes the numbers look better.
DIRECTION: dict[Reading, int] = {
    Reading.LOADED_SPRING: +1,       # crowd arriving before the move
    Reading.QUIET_ACCUMULATION: +1,  # move without the crowd, expected to continue
    Reading.EXIT_LIQUIDITY: -1,      # crowd arriving after it, expected to lag
    Reading.CAPITULATION: 0,         # directionally ambiguous, recorded but not graded
}


@dataclasses.dataclass(frozen=True)
class Event:
    coin_id: int
    symbol: str
    reading: Reading
    opened_at: str
    price_at_open: float
    why: str
    confident: bool


@dataclasses.dataclass(frozen=True)
class Score:
    event: Event
    horizon_h: int
    price_then: float
    coin_return: float
    universe_return: float
    excess_return: float             # what the event is actually judged on
    hit: bool | None                 # None when the reading predicts no direction


def _ts(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def detect(history: list[tuple[Verdict, float]]) -> list[Event]:
    """One asset's verdicts in time order, each with the price at that instant.
    Returns the events it opened."""
    events: list[Event] = []
    run_reading: Reading | None = None
    run_len = 0
    open_reading: Reading | None = None

    for verdict, price in history:
        if verdict.reading is run_reading:
            run_len += 1
        else:
            run_reading, run_len = verdict.reading, 1

        if run_reading is Reading.NOTHING:
            open_reading = None      # a lull re-arms the next reading
            continue

        if run_len == MIN_DWELL and run_reading is not open_reading:
            events.append(Event(
                coin_id=verdict.coin_id, symbol=verdict.symbol, reading=run_reading,
                opened_at=verdict.at, price_at_open=price, why=verdict.why,
                confident=verdict.confident))
            open_reading = run_reading
    return events


def score(event: Event, horizon_h: int, price_then: float,
          universe_returns: list[float]) -> Score | None:
    """Grade one event at one horizon. `universe_returns` is every asset's return over
    the same window, which is what the event has to beat."""
    if not event.price_at_open or not universe_returns:
        return None
    coin_ret = (price_then - event.price_at_open) / event.price_at_open
    uni_ret = statistics.median(universe_returns)
    excess = coin_ret - uni_ret
    direction = DIRECTION.get(event.reading, 0)
    hit = None if direction == 0 else (excess * direction > 0)
    return Score(event=event, horizon_h=horizon_h, price_then=price_then,
                 coin_return=coin_ret, universe_return=uni_ret,
                 excess_return=excess, hit=hit)


@dataclasses.dataclass
class Card:
    reading: Reading
    horizon_h: int
    n: int
    graded: int
    hits: int
    mean_excess: float

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.graded if self.graded else None

    def __str__(self) -> str:
        rate = "n/a" if self.hit_rate is None else f"{self.hit_rate:.0%}"
        return (f"{self.reading.value:<20} +{self.horizon_h:>2}h  "
                f"n={self.n:<4} graded={self.graded:<4} hit={rate:<5} "
                f"mean excess {self.mean_excess:+.2%}")


# A reading is a hypothesis. These thresholds decide when the record is enough to call
# it, and they are deliberately visible: a verdict nobody can check is an opinion.
MIN_TO_JUDGE = 40           # graded readings before the record says anything at all
SUPPORT_HIT = 0.55          # hit rate above which the claim is carrying its weight
REJECT_HIT = 0.45           # and below which the data is arguing with it
MATERIAL_EXCESS = 0.005     # 0.5 pt of mean excess, below which it is noise either way


def verdict(reading: Reading, scores: list[Score],
            confident_only: bool = True) -> tuple[str, str]:
    """What the record says about a reading, in plain words. Returns (verdict, why).

    `evidence` is the mean excess return signed by what the reading claims, so a positive
    number always means "the claim was right" regardless of which way it points. That
    matters for exit_liquidity, which predicts underperformance: its assets going UP is
    the claim failing, and a raw mean would read as success.

    **Only confident readings are graded by default.** A reading made while the crowd
    axis was turnover standing in for a crowd is a different model from one made on a
    measured count of people, and averaging the two reports the accuracy of neither. When
    the attention feed became available mid-run this stopped being hypothetical: pooling
    the two turned a rejected reading into an inconclusive one, which is a real change of
    conclusion produced by nothing but arithmetic.
    """
    direction = DIRECTION.get(reading, 0)
    if direction == 0:
        return "not graded", "This reading claims no direction, so it takes no credit."
    graded = [s for s in scores
              if s.hit is not None and (s.event.confident or not confident_only)]
    if len(graded) < MIN_TO_JUDGE:
        return "too early", (f"Only {len(graded)} graded on a measured crowd axis; "
                             f"{MIN_TO_JUDGE} before calling it.")
    hit = sum(1 for g in graded if g.hit) / len(graded)
    evidence = statistics.fmean([g.excess_return for g in graded]) * direction
    if hit >= SUPPORT_HIT and evidence >= MATERIAL_EXCESS:
        return "supported", (f"{hit:.0%} of {len(graded)} went the way it claimed, "
                             f"worth {evidence:+.2%} of excess return.")
    if hit <= REJECT_HIT and evidence <= -MATERIAL_EXCESS:
        return "rejected", (f"Only {hit:.0%} of {len(graded)} went the way it claimed, and "
                            f"they moved {-evidence:+.2%} the OTHER way. The claim is "
                            f"backwards in the tape recorded so far.")
    return "no edge", (f"{hit:.0%} of {len(graded)}, worth {evidence:+.2%}. "
                       f"Indistinguishable from picking at random.")


def scorecard(scores: list[Score], confident_only: bool = True) -> list[Card]:
    """Aggregate by reading and horizon. Ungraded readings still report n, so a reading
    that is never graded cannot quietly vanish from the report.

    Filtered to confident readings by the same rule `verdict` uses. They were briefly
    computed on different populations, which put a SUPPORTED verdict directly above a
    table saying CONTRADICTS at two of three horizons - both correct, about different
    sets of events, and together meaningless.
    """
    buckets: dict[tuple[Reading, int], list[Score]] = {}
    for s in scores:
        if confident_only and not s.event.confident:
            continue
        buckets.setdefault((s.event.reading, s.horizon_h), []).append(s)

    cards = []
    for (reading, h), group in sorted(buckets.items(),
                                      key=lambda kv: (kv[0][0].value, kv[0][1])):
        graded = [g for g in group if g.hit is not None]
        cards.append(Card(
            reading=reading, horizon_h=h, n=len(group), graded=len(graded),
            hits=sum(1 for g in graded if g.hit),
            mean_excess=statistics.fmean([g.excess_return for g in group]) if group else 0.0,
        ))
    return cards
