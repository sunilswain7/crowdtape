"""
The bot's rendering, against the same JSON the site serves.

The bot never calls CoinMarketCap - it reads the published files - so its whole surface
can be tested with no token, no network and no key. What is pinned here is the honesty:
an unconfirmed reading must say so, and a reading whose own record is 'rejected' or
'no edge' must carry that warning wherever it is shown. A bot that quietly drops those
qualifiers would be a more confident product and a less truthful one.
"""
import json, os, pathlib, re, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_bot(latest, scorecard):
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "stub")
    ns = {"__file__": str(ROOT / "bot" / "telegram.py"), "__name__": "test"}
    exec(compile((ROOT / "bot" / "telegram.py").read_text(), "telegram.py", "exec"), ns)
    sent = []
    ns["site"] = lambda n: {"latest.json": latest, "scorecard.json": scorecard}[n]
    ns["say"] = lambda chat, text: sent.append(text)
    ns["real_log"] = ns["log"]          # keep the real one reachable for the privacy test
    ns["log"] = lambda chat, cmd: None  # command tests must not write to disk
    return ns, sent


def plain(t):
    return re.sub(r"<[^>]+>", "", t)


LATEST = {
    "at": "2026-09-21T03:47:00+00:00", "universe": 200, "median_move_24h": 3.0,
    "attention_available": False, "wallets_covered": 45, "holder_passes": 9,
    "snapshots_recorded": 272, "first_recorded": "2026-09-18T19:59:00+00:00",
    "unavailable": {}, "rows": [
        {"id": 1, "symbol": "AAA", "rank": 5, "price": 2.0, "pct_24h": 9.0,
         "market_cap": 1e9, "volume_24h": 1e8, "reading": "quiet_accumulation",
         "price_state": "up", "attention": "quiet", "leverage": "quiet",
         "why": "Outperforming while interest sits below average.", "confident": True,
         "attention_rank": None, "wallet_count": 8980, "wallet_growth": -0.00045,
         "liq_long_24h": 1.0, "liq_short_24h": 1.0},
        {"id": 2, "symbol": "BBB", "rank": 9, "price": 1.0, "pct_24h": 1.0,
         "market_cap": 1e9, "volume_24h": 1e8, "reading": "exit_liquidity",
         "price_state": "up", "attention": "rising", "leverage": "unknown",
         "why": "Interest arriving after the move, not before it.", "confident": False,
         "attention_rank": None, "wallet_count": None, "wallet_growth": None,
         "liq_long_24h": None, "liq_short_24h": None},
        {"id": 3, "symbol": "CCC", "rank": 1, "price": 100.0, "pct_24h": 1.0,
         "market_cap": 1e12, "volume_24h": 1e9, "reading": "nothing",
         "price_state": "flat", "attention": "steady", "leverage": "quiet",
         "why": "Nothing separating this from the rest of the tape.", "confident": False,
         "attention_rank": None, "wallet_count": None, "wallet_growth": None,
         "liq_long_24h": 1.0, "liq_short_24h": 1.0},
    ]}
SCORE = {"generated_at": "2026-09-21T04:00:00+00:00", "events_total": 355,
         "events_graded": 247, "cards": [], "verdicts": {
             "quiet_accumulation": {"verdict": "no edge", "n": 177,
                                    "why": "42% of 177, worth -0.08%."},
             "exit_liquidity": {"verdict": "rejected", "n": 82,
                                "why": "Only 38% went the way it claimed."},
             "loaded_spring": {"verdict": "supported", "n": 76,
                               "why": "61% of 76 went the way it claimed."}}}


class Board(unittest.TestCase):
    def test_lists_only_assets_carrying_a_reading(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_board"](1, [])
        t = plain(sent[0])
        self.assertIn("AAA", t); self.assertIn("BBB", t)
        self.assertNotIn("CCC", t, "an asset with no reading is not news")

    def test_shows_the_move_against_the_market_not_just_the_raw_move(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_board"](1, [])
        self.assertIn("vs mkt", plain(sent[0]))

    def test_marks_unconfirmed_readings(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_board"](1, [])
        line = [l for l in plain(sent[0]).splitlines() if "BBB" in l][0]
        self.assertIn("unconfirmed", line)
        self.assertNotIn("unconfirmed", [l for l in plain(sent[0]).splitlines()
                                         if "AAA" in l][0])

    def test_says_when_the_attention_feed_is_missing(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_board"](1, [])
        self.assertIn("most-visited", plain(sent[0]))

    def test_an_empty_board_is_stated_not_blank(self):
        ns, sent = load_bot({**LATEST, "rows": [LATEST["rows"][2]]}, SCORE)
        ns["cmd_board"](1, [])
        self.assertIn("real answer", plain(sent[0]))


class Coin(unittest.TestCase):
    def test_warns_when_the_readings_own_record_is_bad(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_coin"](1, ["AAA"])
        t = plain(sent[0])
        self.assertIn("no edge", t)
        self.assertIn("42% of 177", t)

    def test_shows_wallet_counts_when_measured(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_coin"](1, ["AAA"])
        self.assertIn("8,980", plain(sent[0]))

    def test_explains_why_a_reading_is_unconfirmed(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_coin"](1, ["BBB"])
        self.assertIn("turnover standing in", plain(sent[0]))

    def test_case_and_dollar_prefix_are_tolerated(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_coin"](1, ["$aaa"])
        self.assertIn("rank 5", plain(sent[0]))

    def test_an_unknown_symbol_says_what_the_universe_is(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_coin"](1, ["NOPE"])
        self.assertIn("top 200", plain(sent[0]))

    def test_no_symbol_asks_for_one(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_coin"](1, [])
        self.assertIn("/coin BTC", plain(sent[0]))


class Score(unittest.TestCase):
    def test_reports_the_rejected_reading_rather_than_hiding_it(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_score"](1, [])
        t = plain(sent[0])
        self.assertIn("REJECTED", t)
        self.assertIn("Misses included", t)

    def test_covers_every_reading_with_a_verdict(self):
        ns, sent = load_bot(LATEST, SCORE)
        ns["cmd_score"](1, [])
        t = plain(sent[0])
        for word in ("SUPPORTED", "REJECTED", "NO EDGE"):
            self.assertIn(word, t)


class Privacy(unittest.TestCase):
    def test_usage_log_records_a_hash_never_the_chat_id(self):
        import hashlib, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CROWDTAPE_DATA_DIR"] = tmp
            try:
                ns, _ = load_bot(LATEST, SCORE)
                ns["real_log"](987654321, "board")
                written = (pathlib.Path(tmp) / "bot-usage.jsonl").read_text()
            finally:
                os.environ.pop("CROWDTAPE_DATA_DIR", None)
        self.assertNotIn("987654321", written)
        rec = json.loads(written)
        self.assertEqual(rec["command"], "board")
        self.assertEqual(rec["user"],
                         hashlib.sha256(b"crowdtape:987654321").hexdigest()[:12])


if __name__ == "__main__":
    unittest.main()
