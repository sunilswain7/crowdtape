# Where this stands

Updated 19 September 2026. Submissions close **30 September 2026, 23:59 UTC**.

## Still on the Basic tier

As of the 05:09 UTC snapshot on 19 Sep, every attention endpoint still answers
**403 "Your API Key subscription plan doesn't support this endpoint"**. The account was
registered on 18 Sep and the upgrade was promised within 24 hours. It has not arrived.
**Escalate on the DoraHacks Q&A tab now.** Another entrant sat on Basic through day 4 of
their build and shipped with a crippled product because of it.

Everything else works on Basic and is recording.

## Blocked on exactly one thing

`docs/endpoint-access.md` and `docs/payload-shapes.md` do not exist yet. They are written
by `scripts/probe.py` and committed by the `probe` workflow.

**To unblock:** Actions tab → click **probe** in the left sidebar → **Run workflow** ▾ →
green **Run workflow**. Do not use *Re-run all jobs* on an old run — that replays the
commit the run was created from, which is how the first two attempts produced nothing.

Everything downstream waits on this. The `liquidations` and `most-visited` payload shapes
have never been observed on a live key, so the field names in `engine/normalize.py` are
candidates rather than facts, and no UI gets built on top of guesses.

## Built and tested

| Piece | File | State |
|---|---|---|
| Capability probe | `scripts/probe.py` | ✅ publishes a measured access table |
| Snapshot recorder | `recorder/record.py` | ✅ never run against a live key |
| Transport | `recorder/net.py` | ✅ DoH + edge rotation |
| Recorder loop | `recorder/loop.py` | ✅ self-clocking, replaces cron |
| Normalisers | `engine/normalize.py` | ✅ liquidations observed; attention still unseen |
| Classifier | `engine/signal.py` | ✅ |
| Events + scorecard | `engine/events.py` | ✅ |
| Tests | `tests/` | ✅ 40, green in CI |

## Not started

Web app, Telegram bot, MCP tool, demo video, X post, DoraHacks submission.

## Open questions the probe answers

1. **What tier is the key on?** 15,000 credits = Basic, 450,000 = Startup. The account was
   registered on 18 Sep and CMC's discussions say the upgrade lands within 24 hours.
   **If it has not landed by 19 Sep, escalate on the DoraHacks Q&A tab** — another entrant
   sat on Basic through day 4 of their build with no resolution.
2. **Does `trending/most-visited` answer, and how deep?** Pass `limit=200` to find the
   ceiling. The whole attention thesis rests on this.
3. **Does it carry a magnitude, or only an ordering?** Magnitude means the signal is
   attention *level*; ordering only means it is rank *velocity*. Different engine shape.

## Then, in order

1. Run `record` once by hand. Every hour without it is data that cannot be recovered,
   because CoinMarketCap retains no history for either attention or positioning.
2. Correct `engine/normalize.py` from `docs/payload-shapes.md`.
3. Raise the recorder to `*/5` in `.github/workflows/record.yml` once the credit ceiling
   is 450,000. On Basic at `*/15` it costs roughly 480 credits a day against a 15,000 cap.
4. Web app: the hero visual is one chart — attention curve over price curve.
5. Telegram bot, so the submission can report real usage rather than claim usefulness.
6. `FEEDBACK.md`: attention and positioning are CoinMarketCap's two most differentiated
   datasets and neither has a history endpoint. That is the note the organisers said is
   worth more to them than any submission.
