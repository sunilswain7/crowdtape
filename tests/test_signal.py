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


def coin(cid=1, sym="AAA", mc=1e9, vol=1e8, pct24=0.0, att=None, lo=None, sh=None):
    return CoinState(at="2026-09-18T00:00:00Z", coin_id=cid, symbol=sym, price=1.0,
                     market_cap=mc, volume_24h=vol, pct_24h=pct24,
                     attention_rank=att, liq_long_24h=lo, liq_short_24h=sh)


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
        self.assertIs(classify_leverage(coin()), Leverage.UNKNOWN)

    def test_small_liquidations_are_quiet(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=1e5, sh=1e5)), Leverage.QUIET)

    def test_lopsided_flush(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=9e6, sh=1e6)), Leverage.LONGS_FLUSHING)
        self.assertIs(classify_leverage(coin(mc=1e9, lo=1e6, sh=9e6)), Leverage.SHORTS_SQUEEZED)

    def test_balanced_heavy_liquidation_is_not_lopsided(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=5e6, sh=5e6)), Leverage.QUIET)

    def test_zero_liquidations_is_quiet_not_a_divide_by_zero(self):
        self.assertIs(classify_leverage(coin(mc=1e9, lo=0.0, sh=0.0)), Leverage.QUIET)


class Readings(unittest.TestCase):
    def setUp(self):
        # a universe wide enough for the cross-sectional z-score to mean something
        self.filler = [coin(cid=100 + i, sym=f"F{i}", vol=1e8) for i in range(30)]

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

    def test_quiet_accumulation(self):
        v = self.verdict_for(coin(att=20, pct24=7.0, mc=1e9, lo=1e5, sh=1e5),
                             prev=coin(att=20))
        self.assertIs(v.reading, Reading.QUIET_ACCUMULATION)

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
