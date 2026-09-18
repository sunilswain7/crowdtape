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


def scorecard(scores: list[Score]) -> list[Card]:
    """Aggregate by reading and horizon. Ungraded readings still report n, so a reading
    that is never graded cannot quietly vanish from the report."""
    buckets: dict[tuple[Reading, int], list[Score]] = {}
    for s in scores:
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
