# Where this stands

Updated 21 September 2026. Submissions close **30 September 2026, 23:59 UTC** — 9 days.

## Live

- **Board:** https://sunilswain7.github.io/crowdtape/
- **Bot:** [@crowdtape_bot](https://t.me/crowdtape_bot) — `/board`, `/coin BTC`, `/score`, `/why`

## The tier never arrived, and the product no longer needs it

Measured 21 Sep: plan is **Basic (free)**, 15,000 credits. Every attention endpoint still
answers 403. The organiser replied on 21 Sep that the upgrade is "likely today"; it has
not landed. The `most_visited` normaliser is in place and starts producing with no code
change if it ever does.

The crowd axis is **wallet counts** instead — `/v1/dex/holders/count`, which answers on
Basic. `holders/trend/list` is 403, so the trend is computed from counts we record. 45 of
the top 200 are covered; the rest have no contract address CMC's DEX index reaches.

## Built and working

| Piece | File | State |
|---|---|---|
| Probe + parameter sweep | `scripts/probe.py` | ✅ publishes measured access table |
| Recorder | `recorder/record.py` | ✅ 10-min snapshots, ~37 KB each |
| Holder pass | `recorder/record.py` | ✅ 50 tokens every 3 hours |
| Self-clocking loop | `recorder/loop.py` | ✅ |
| Transport | `recorder/net.py` | ✅ DoH + edge rotation past the ISP block |
| Engine | `engine/` | ✅ cross-sectional, wallet-driven crowd axis |
| Scorecard verdicts | `engine/events.py` | ✅ supported / rejected / no edge |
| Site generator | `engine/report.py` | ✅ |
| Dashboard | `site/index.html` | ✅ live |
| Telegram bot | `bot/telegram.py` | ✅ live, usage committed every 10 min |
| `FEEDBACK.md` | | ✅ eight findings, all measured |
| Tests | `tests/` | ✅ 65, green in CI |

## The scorecard's own verdict

272 snapshots, 355 readings issued, 247 graded:

| Reading | Verdict | Evidence |
|---|---|---|
| Loaded spring | **SUPPORTED** | 61% of 76, +1.43% excess |
| Exit liquidity | **REJECTED** | 38% of 82, moved +2.01% the *other* way |
| Quiet accumulation | **NO EDGE** | 42% of 177, −0.08% |
| Capitulation | **NOT GRADED** | claims no direction |

`exit_liquidity` is inverted in the tape recorded so far. **Do not flip the sign.** One
strong uptrend is not enough to rewrite a hypothesis, and publishing the failure is worth
more than a flattering table — every rival asserts their signal works.

## Not started

`JUDGE.md` · demo video · X post with #BuildwithCMC · DoraHacks submission.

## Next, in order

1. **`JUDGE.md`.** The strongest rivals have one. Ours has an unusual 60-second story:
   the signal we set out to build is plan-gated, we replaced it with wallet counts, and
   our own scorecard says one of our four readings is backwards.
2. **Share the bot.** Usage is 25 of 100 points, accumulates in days not minutes, and is
   the one piece of evidence no rival can manufacture on submission day.
3. **Demo video** (2 min) and the X post. Leave two clear days.
4. If the tier lands: drop `SNAPSHOT_INTERVAL_S` to 180 and correct the `most_visited`
   normaliser from the first observed payload.

## Gotchas to remember

- `site/data/*.json` is generated; on a rebase conflict, regenerate, never merge by hand.
- Commit messages go through a file (`git commit -F`) — backticks in `-m` trigger shell
  substitution and have broken a commit before.
- A local probe run overwrites the real measured reports unless `PROBE_DOCS_DIR` is set.
