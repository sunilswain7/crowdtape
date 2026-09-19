# Where this stands

Updated 19 September 2026, midday. Submissions close **30 September 2026, 23:59 UTC**.

## Two things waiting on someone else

1. **The Startup tier upgrade has not landed.** Every `most-visited` call has answered
   403 since the key was issued. Escalated on the DoraHacks Q&A tab on 19 Sep; nothing to
   do but wait. The product works without it, at reduced confidence, and sharpens
   automatically the moment it arrives - no code change.
2. **GitHub Pages is not enabled.** The deploy workflow is committed and will publish on
   every recorder commit. Turn it on at **Settings → Pages → Source: "GitHub Actions"**
   to get the live URL the submission requires.

## Built and working

| Piece | File | State |
|---|---|---|
| Capability probe | `scripts/probe.py` | ✅ publishes a measured access table |
| Snapshot recorder | `recorder/record.py` | ✅ running, ~37 KB per snapshot |
| Self-clocking loop | `recorder/loop.py` | ✅ 10-minute snapshots |
| Transport | `recorder/net.py` | ✅ DoH + edge rotation |
| Normalisers | `engine/normalize.py` | ✅ liquidations observed; attention unseen |
| Classifier | `engine/signal.py` | ✅ fully cross-sectional |
| Events + scorecard | `engine/events.py` | ✅ grading live |
| Site data generator | `engine/report.py` | ✅ |
| Dashboard | `site/index.html` | ✅ validated palette, rendered and checked |
| Tests | `tests/` | ✅ 40, green in CI |

## What real data changed

Running on the first recorded snapshots broke three assumptions, and each fix is worth
keeping in mind before adding anything new:

- **Cron does not work.** `*/15` produced four runs in nine hours. The schedule now only
  starts a job and `recorder/loop.py` holds it open.
- **Everything must be cross-sectional.** On a day the market rose 4.2%, an absolute
  price test called 126 of 200 assets a signal. Price is judged on excess over the
  universe median, liquidation stress on rank within the universe.
- **Absence of evidence is not evidence of absence.** `quiet_accumulation` requires
  *measured* low interest. Absent from a readable most-visited list is evidence; absent
  because the endpoint is gated is not.
- **Stablecoins break relative measures.** Every peg underperforms a rising market. They
  are excluded from readings and from the median.

## Not started

Telegram bot · `FEEDBACK.md` · demo video · X post · DoraHacks submission.

## Next, in order

1. **Enable Pages** and confirm the board is live.
2. **Telegram bot.** This is the differentiator on "usefulness to a real person": every
   rival submission is a web app a judge clicks once. Real usage numbers cannot be faked
   on submission day and cannot be caught up on later.
3. **`FEEDBACK.md`** while the friction is fresh: attention and positioning are
   CoinMarketCap's two most differentiated datasets and neither has a history endpoint;
   a non-existent path answers HTTP 200; `/v1/key/info` reports no tier name. The
   organisers said this note is worth more to them than any submission.
4. **Demo video and submission.** Leave two clear days.
5. If the tier lands: drop `SNAPSHOT_INTERVAL_S` to 180 in `.github/workflows/record.yml`
   (450,000 credits absorbs it easily) and correct the `most_visited` normaliser from the
   first observed payload.
