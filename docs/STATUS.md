# Where this stands

Updated 22 September 2026. Submissions close **30 September 2026, 23:59 UTC** — 8 days.

## Live

- **Board:** https://sunilswain7.github.io/crowdtape/ — Next.js, four routes
- **Bot:** [@crowdtape_bot](https://t.me/crowdtape_bot) — `/crowd`, `/board`, `/coin`, `/score`, `/why`

## The upgrade landed on 21 Sep

450,000 credits, 600 req/min, and `trending/most-visited` answers at all three horizons.
The payload settled the question this project had open since day one: **there is no
magnitude** — no view count, no traffic score. `cmc_rank` in that response is the
market-cap rank. Attention is the position in the list and nothing else.

The 24h stream also carries a full quote, so assets too small for the top 200 arrive
complete. The universe is now the **union** of the market-cap listing and the attention
list — 275 assets, ~75 attention-only. The most looked-up asset on CoinMarketCap sat at
market-cap rank 682 the day this was written; a top-200 screener cannot see it.

## Built

| Piece | Where | State |
|---|---|---|
| Probe + parameter sweep | `scripts/probe.py` | ✅ |
| Recorder + holder pass | `recorder/` | ✅ 10-min snapshots, 138 tokens every 30 min |
| Engine | `engine/` | ✅ attention-driven, fully cross-sectional |
| Scorecard verdicts | `engine/events.py` | ✅ graded on a measured crowd axis only |
| Board | `web/` (Next.js) | ✅ live |
| Telegram bot | `bot/telegram.py` | ✅ live, usage committed every 10 min |
| `FEEDBACK.md`, `JUDGE.md` | | ✅ |
| Tests | `tests/` | ✅ 78 |

## The scorecard is deliberately inconclusive

Readings made while the crowd axis was **turnover standing in for a crowd** are not graded
alongside readings made on a **measured count of people**. Pooling them turned a rejected
reading into an inconclusive one on arithmetic alone, which is a changed conclusion
produced by nothing but averaging two incompatible models.

As of 22 Sep: 24–27 graded per reading on the measured axis, against a threshold of 40, so
every verdict reads **TOO EARLY**. That will cross within a day now the feed is live.
Before the split, on the proxy, `exit_liquidity` came out **rejected** — its assets
outperformed when it predicted underperformance.

**Do not flip a sign to improve the table.** The honest record is the differentiator.

## Not started — all of it is the user's

Demo video · X post · DoraHacks submission · sharing the bot.

`launch-kit.md` (gitignored, not part of the submission) holds the video script, the X
thread, and the Reddit/Discord copy including the "why should I trust this?" answer.

## Next, in order

1. **Restart `record`** — the running job predates the zero-market-cap fix, so assets with
   unverified supply still show `$0` instead of `—`.
2. **Share the bot.** Usage is 25 of 100 points, accumulates in days, and cannot be
   manufactured on submission day. `r/algotrading` first — that community respects
   published negative results.
3. **Film after the scorecard crosses 40 confident grades.** The story lands far harder
   when the screen reads REJECTED while the narration explains the sign was not flipped.
4. X post, DoraHacks form. Leave two clear days.

## Gotchas

- `site/data/*.json` is generated; on a rebase conflict regenerate, never merge by hand.
- Commit messages go through a file (`git commit -F`) — backticks in `-m` trigger shell
  substitution and have broken a commit before.
- A local probe run overwrites the real measured reports unless `PROBE_DOCS_DIR` is set;
  a local recorder run needs `CROWDTAPE_DATA_DIR`.
- The Next app is a **static export**: it fetches `data/*.json` at runtime, so data updates
  need no rebuild. The data URL comes from `NEXT_PUBLIC_BASE_PATH` — deriving it from
  `window.location` breaks on nested routes.
