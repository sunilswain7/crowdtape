"""
Tests for the classifier. No key, no network, no recorded data required - the engine
reads canonical records, so its behaviour is pinned independently of whatever shape
CoinMarketCap turns out to return.

    python3 -m unittest discover -s tests -v
"""
import unittest
from engine.normalize import CoinState, from_snapshot
from engine.signal import (Attention, Leverage, Price, Reading, classify,
                           classify_attention, classify_leverage, classify_price)


def coin(cid=1, sym="AAA", mc=1e9, vol=1e8, pct24=0.0, att=None, lo=None, sh=None,
         att_avail=False, stable=None):
    return CoinState(at="2026-09-18T00:00:00Z", coin_id=cid, symbol=sym, price=1.0,
                     market_cap=mc, volume_24h=vol, pct_24h=pct24,
                     attention_rank=att, attention_available=att_avail,
                     is_stablecoin=stable, liq_long_24h=lo, liq_short_24h=sh)


QUIET_CUT = 0.002   # a universe whose upper-quartile liquidation intensity is 0.2%


class Price_(unittest.TestCase):
    def test_bands(self):
        self.assertIs(classify_price(coin(pct24=5)), Price.UP)
        self.assertIs(classify_price(coin(pct24=-5)), Price.DOWN)
        self.assertIs(classify_price(coin(pct24=1.9)), Price.FLAT)

    def test_boundary_is_inclusive(self):
        self.assertIs(classify_price(coin(pct24=2.0)), Price.UP)
        self.assertIs(classify_price(coin(pct24=-2.0)), Price.DOWN)

    def test_missing_is_flat_not_a_crash(self):
        self.assertIs(classify_price(CoinState(at="", coin_id=1, symbol="A")), Price.FLAT)


class Attention_(unittest.TestCase):
    def test_appearing_on_the_list_is_the_event(self):
        self.assertIs(classify_attention(coin(att=40), coin(att=None), None),
                      Attention.RISING)

    def test_climbing_the_list(self):
        self.assertIs(classify_attention(coin(att=10), coin(att=30), None), Attention.RISING)
        self.assertIs(classify_attention(coin(att=28), coin(att=30), None), Attention.STEADY)

    def test_falling_down_the_list_is_not_rising(self):
        self.assertIs(classify_attention(coin(att=30), coin(att=10), None), Attention.STEADY)

    def test_turnover_fallback_only_without_attention(self):
        self.assertIs(classify_attention(coin(att=None), None, 2.0), Attention.RISING)
        self.assertIs(classify_attention(coin(att=None), None, 0.2), Attention.STEADY)
        # a real attention rank must win over the proxy, even a screaming one
        self.assertIs(classify_attention(coin(att=99), coin(att=99), 9.0), Attention.STEADY)

    def test_unknown_when_neither_available(self):
        self.assertIs(classify_attention(coin(att=None), None, None), Attention.UNKNOWN)


class Leverage_(unittest.TestCase):
    def test_unknown_without_liquidations(self):
        self.assertIs(classify_leverage(coin(), QUIET_CUT), Leverage.UNKNOWN)

    def test_no_cutoff_means_quiet_rather_than_a_guess(self):
        """With no universe to rank against there is no such thing as unusual stress."""
        self.assertIs(classify_leverage(coin(mc=1e9, lo=9e6, sh=1e6), None), Leverage.QUIET)

    def test_below_the_universe_cutoff_is_quiet(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=1e5, sh=1e5), QUIET_CUT), Leverage.QUIET)

    def test_lopsided_flush(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=9e6, sh=1e6), QUIET_CUT),
                      Leverage.LONGS_FLUSHING)
        self.assertIs(classify_leverage(coin(mc=1e9, lo=1e6, sh=9e6), QUIET_CUT),
                      Leverage.SHORTS_SQUEEZED)

    def test_balanced_heavy_liquidation_is_not_lopsided(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=5e6, sh=5e6), QUIET_CUT), Leverage.QUIET)

    def test_zero_liquidations_is_quiet_not_a_divide_by_zero(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=0.0, sh=0.0), QUIET_CUT), Leverage.QUIET)


class Readings(unittest.TestCase):
    def setUp(self):
        # A universe wide enough for the cross-sectional measures to mean something, and
        # carrying liquidations of its own so an upper-quartile cutoff exists at all.
        self.filler = [coin(cid=100 + i, sym=f"F{i}", vol=1e8, lo=1e5, sh=1e5)
                       for i in range(30)]

    def verdict_for(self, subject, prev=None):
        states = [subject] + self.filler
        prevs = {prev.coin_id: prev} if prev else {}
        return next(v for v in classify(states, prevs) if v.coin_id == subject.coin_id)

    def test_loaded_spring(self):
        v = self.verdict_for(coin(att=5, pct24=0.4, mc=1e9, lo=1e5, sh=1e5),
                             prev=coin(att=40))
        self.assertIs(v.reading, Reading.LOADED_SPRING)
        self.assertTrue(v.confident)

    def test_exit_liquidity(self):
        v = self.verdict_for(coin(att=3, pct24=12.0, mc=1e9, lo=1e5, sh=1e5),
                             prev=coin(att=50))
        self.assertIs(v.reading, Reading.EXIT_LIQUIDITY)

    def test_capitulation(self):
        v = self.verdict_for(coin(att=2, pct24=-14.0, mc=1e9, lo=9e6, sh=1e6),
                             prev=coin(att=60))
        self.assertIs(v.reading, Reading.CAPITULATION)
        self.assertIs(v.leverage, Leverage.LONGS_FLUSHING)

    def test_quiet_accumulation_needs_measured_quiet_not_merely_unmeasured(self):
        """Outperforming while on the most-visited list is not quiet accumulation."""
        on_the_list = self.verdict_for(coin(att=20, pct24=7.0, mc=1e9, lo=1e5, sh=1e5),
                                       prev=coin(att=20))
        self.assertIsNot(on_the_list.reading, Reading.QUIET_ACCUMULATION)

        # absent from a list that WAS readable is a measurement of low interest
        absent = self.verdict_for(coin(att=None, att_avail=True, pct24=7.0,
                                       mc=1e9, lo=1e5, sh=1e5))
        self.assertIs(absent.reading, Reading.QUIET_ACCUMULATION)

    def test_a_stablecoin_is_not_read_on_a_relative_price_measure(self):
        """Every peg underperforms a rising market. That is not capitulation."""
        v = self.verdict_for(coin(sym="FDUSD", pct24=0.0, stable=True), prev=None)
        self.assertIs(v.reading, Reading.NOTHING)
        self.assertIn("Stablecoin", v.why)

    def test_confidence_is_withheld_without_the_attention_stream(self):
        # exactly today's situation: Basic tier, attention gated, turnover standing in
        v = self.verdict_for(coin(att=None, pct24=0.1, vol=9e9, mc=1e9, lo=1e5, sh=1e5))
        self.assertIs(v.reading, Reading.LOADED_SPRING)
        self.assertFalse(v.confident)

    def test_thin_universe_does_not_fabricate_a_z_score(self):
        subject = coin(att=None, pct24=0.1, vol=9e9)
        v = next(x for x in classify([subject, coin(cid=2)]) if x.coin_id == 1)
        self.assertIs(v.attention, Attention.UNKNOWN)
        self.assertIs(v.reading, Reading.NOTHING)


class Normalising(unittest.TestCase):
    def test_a_gated_stream_is_recorded_not_invented(self):
        snap = {"at": "2026-09-18T00:00:00Z", "streams": {
            "listings": {"axis": "price", "http": 200,
                         "data": [{"id": 1, "s": "BTC", "p": 50.0, "mc": 1e9,
                                   "v": 1e8, "r": 1, "c24": 3.0}]},
            "most_visited_24h": {"axis": "attention", "http": 403,
                                 "error": "Your API Key subscription plan..."},
        }}
        states, notes = from_snapshot(snap)
        self.assertEqual(len(states), 1)
        self.assertIsNone(states[0].attention_rank)
        self.assertIn("most_visited_24h", notes)

    def test_derived_metrics(self):
        s = coin(mc=1e9, vol=5e8, lo=3.0, sh=1.0)
        self.assertAlmostEqual(s.turnover, 0.5)
        self.assertAlmostEqual(s.liq_total_24h, 4.0)
        self.assertAlmostEqual(s.long_share, 0.75)

    def test_no_market_cap_means_no_turnover_rather_than_infinity(self):
        self.assertIsNone(coin(mc=0, vol=1e8).turnover)


if __name__ == "__main__":
    unittest.main()


class AttentionDepth(unittest.TestCase):
    """With a 200-deep list, merely being on it is not an event.

    Treating arrival anywhere on the list as news fired a reading on three quarters of
    the universe the first time the real feed was read, which is why these exist.
    """

    def test_arriving_deep_in_the_list_is_not_an_event(self):
        deep = coin(att=197, att_avail=True)
        self.assertIs(classify_attention(deep, None, None), Attention.STEADY)

    def test_arriving_high_in_the_list_is_an_event(self):
        high = coin(att=12, att_avail=True)
        self.assertIs(classify_attention(high, None, None), Attention.RISING)

    def test_climbing_is_an_event_wherever_it_happens(self):
        now, before = coin(att=120, att_avail=True), coin(att=180, att_avail=True)
        self.assertIs(classify_attention(now, before, None), Attention.RISING)

    def test_attention_far_better_on_24h_than_30d_is_accelerating(self):
        """Interest that did not exist a month ago, established without our own history."""
        c = CoinState(at="", coin_id=1, symbol="MALA", market_cap=1e8, volume_24h=1e7,
                      attention_rank=4, attention_rank_30d=90,
                      attention_available=True, attention_30d_available=True)
        self.assertIs(classify_attention(c, None, None), Attention.RISING)

    def test_a_standing_crowd_is_steady_not_rising(self):
        """High on every horizon means the crowd is already there, not arriving."""
        c = CoinState(at="", coin_id=1, symbol="BTC", market_cap=1e12, volume_24h=1e10,
                      attention_rank=2, attention_rank_30d=2,
                      attention_available=True, attention_30d_available=True)
        self.assertIs(classify_attention(c, c, None), Attention.STEADY)

    def test_an_unread_30d_list_is_not_treated_as_absence(self):
        """The flag distinguishes "not on the list" from "never looked"."""
        unread = CoinState(at="", coin_id=1, symbol="X", market_cap=1e8, volume_24h=1e7,
                           attention_rank=28, attention_rank_30d=None,
                           attention_available=True, attention_30d_available=False)
        self.assertIs(classify_attention(unread, unread, None), Attention.STEADY)

    def test_absent_from_the_30d_list_counts_as_past_its_end(self):
        c = CoinState(at="", coin_id=1, symbol="NEW", market_cap=1e8, volume_24h=1e7,
                      attention_rank=150, attention_rank_30d=None,
                      attention_available=True, attention_30d_available=True)
        self.assertIs(classify_attention(c, c, None), Attention.RISING)

    def test_absence_from_the_list_is_still_measured_quiet(self):
        self.assertIs(classify_attention(coin(att=None, att_avail=True), None, None),
                      Attention.QUIET)
