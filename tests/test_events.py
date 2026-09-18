"""Event detection and grading. No key, no network, no recorded data."""
import unittest
from engine.events import (MIN_DWELL, Card, Event, detect, score, scorecard)
from engine.signal import Reading, Verdict


def v(reading, at="2026-09-18T00:00:00Z", cid=1, confident=True):
    return Verdict(coin_id=cid, symbol="AAA", at=at, reading=reading,
                   price=None, attention=None, leverage=None,
                   why="because", confident=confident)


def series(*readings, start_price=100.0):
    return [(v(r, at=f"2026-09-18T{i:02d}:00:00Z"), start_price) for i, r in enumerate(readings)]


class Detection(unittest.TestCase):
    def test_a_single_snapshot_does_not_open_an_event(self):
        self.assertEqual(detect(series(Reading.LOADED_SPRING)), [])

    def test_opens_once_the_reading_holds(self):
        ev = detect(series(Reading.LOADED_SPRING, Reading.LOADED_SPRING))
        self.assertEqual(len(ev), 1)
        self.assertIs(ev[0].reading, Reading.LOADED_SPRING)
        self.assertEqual(ev[0].opened_at, "2026-09-18T01:00:00Z")

    def test_a_held_reading_opens_exactly_one_event(self):
        ev = detect(series(*[Reading.LOADED_SPRING] * 8))
        self.assertEqual(len(ev), 1, "a persistent situation is one event, not eight")

    def test_flapping_on_a_threshold_does_not_manufacture_events(self):
        ev = detect(series(Reading.LOADED_SPRING, Reading.NOTHING,
                           Reading.LOADED_SPRING, Reading.NOTHING,
                           Reading.LOADED_SPRING, Reading.NOTHING))
        self.assertEqual(ev, [], "no reading ever held for MIN_DWELL")

    def test_a_lull_rearms_the_same_reading(self):
        ev = detect(series(Reading.LOADED_SPRING, Reading.LOADED_SPRING,
                           Reading.NOTHING, Reading.NOTHING,
                           Reading.LOADED_SPRING, Reading.LOADED_SPRING))
        self.assertEqual(len(ev), 2, "the situation genuinely recurred")

    def test_changing_reading_opens_a_new_event(self):
        ev = detect(series(Reading.LOADED_SPRING, Reading.LOADED_SPRING,
                           Reading.EXIT_LIQUIDITY, Reading.EXIT_LIQUIDITY))
        self.assertEqual([e.reading for e in ev],
                         [Reading.LOADED_SPRING, Reading.EXIT_LIQUIDITY])

    def test_nothing_never_opens_an_event(self):
        self.assertEqual(detect(series(*[Reading.NOTHING] * 5)), [])

    def test_dwell_constant_is_what_the_tests_assume(self):
        self.assertEqual(MIN_DWELL, 2)


def ev(reading, price=100.0):
    return Event(coin_id=1, symbol="AAA", reading=reading,
                 opened_at="2026-09-18T00:00:00Z", price_at_open=price,
                 why="because", confident=True)


class Grading(unittest.TestCase):
    def test_beating_the_market_is_a_hit_for_an_upside_reading(self):
        s = score(ev(Reading.LOADED_SPRING), 24, 110.0, [0.02, 0.03, 0.04])
        self.assertAlmostEqual(s.coin_return, 0.10)
        self.assertAlmostEqual(s.universe_return, 0.03)
        self.assertAlmostEqual(s.excess_return, 0.07)
        self.assertTrue(s.hit)

    def test_rising_less_than_the_market_is_not_a_hit(self):
        s = score(ev(Reading.LOADED_SPRING), 24, 104.0, [0.06, 0.06, 0.06])
        self.assertTrue(s.coin_return > 0, "it went up")
        self.assertFalse(s.hit, "but it lagged a coin picked at random")

    def test_exit_liquidity_is_graded_the_other_way(self):
        lag = score(ev(Reading.EXIT_LIQUIDITY), 24, 101.0, [0.05, 0.05, 0.05])
        self.assertTrue(lag.hit, "predicted underperformance and underperformed")
        lead = score(ev(Reading.EXIT_LIQUIDITY), 24, 120.0, [0.01, 0.01, 0.01])
        self.assertFalse(lead.hit)

    def test_an_ambiguous_reading_is_recorded_but_not_graded(self):
        s = score(ev(Reading.CAPITULATION), 24, 130.0, [0.0, 0.0])
        self.assertIsNone(s.hit, "no direction claimed, so no credit taken")

    def test_no_universe_means_no_score_rather_than_a_guess(self):
        self.assertIsNone(score(ev(Reading.LOADED_SPRING), 24, 110.0, []))

    def test_zero_open_price_does_not_divide_by_zero(self):
        self.assertIsNone(score(ev(Reading.LOADED_SPRING, price=0.0), 24, 1.0, [0.01]))


class Scorecard(unittest.TestCase):
    def test_aggregates_and_reports_misses(self):
        uni = [0.0, 0.0, 0.0]
        scores = [
            score(ev(Reading.LOADED_SPRING), 24, 110.0, uni),   # hit
            score(ev(Reading.LOADED_SPRING), 24, 120.0, uni),   # hit
            score(ev(Reading.LOADED_SPRING), 24, 90.0, uni),    # miss
        ]
        card = scorecard(scores)[0]
        self.assertEqual((card.n, card.graded, card.hits), (3, 3, 2))
        self.assertAlmostEqual(card.hit_rate, 2 / 3)
        self.assertAlmostEqual(card.mean_excess, (0.10 + 0.20 - 0.10) / 3)

    def test_an_ungraded_reading_still_appears_in_the_report(self):
        cards = scorecard([score(ev(Reading.CAPITULATION), 4, 130.0, [0.0])])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].n, 1)
        self.assertEqual(cards[0].graded, 0)
        self.assertIsNone(cards[0].hit_rate, "cannot vanish just because it is not graded")


if __name__ == "__main__":
    unittest.main()
