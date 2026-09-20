# Where this stands

Updated 20 September 2026, midday. Submissions close **30 September 2026, 23:59 UTC**.

## Live

**https://sunilswain7.github.io/crowdtape/** — published from this repository on every
recorder commit.

## The tier never arrived, and the product no longer depends on it

Measured 20 Sep, published in `endpoint-access.md`: the plan is **Basic (free)**, 15,000
credits. Every attention endpoint answers 403. Escalated on DoraHacks on 19 Sep, no
response.

The crowd axis is now **wallet counts** instead. `/v1/dex/holders/count` answers on Basic
and returns how many distinct wallets hold a token — an actual measurement, not the
turnover proxy. `/v1/dex/holders/trend/list` answers **403**, so the series exists nowhere
unless somebody records the counts. That is the same argument as the rest of the project,
handed over by CoinMarketCap's own tier boundary.

If the upgrade ever lands, the `most_visited` normaliser is still in place and starts
producing without a code change.

## Built and working

| Piece | File | State |
|---|---|---|
| Capability probe + parameter sweep | `scripts/probe.py` | ✅ publishes the measured table |
| Recorder | `recorder/record.py` | ✅ 10-min snapshots, ~37 KB each |
| Holder pass | `recorder/record.py` | ✅ 50 tokens every 3 hours |
| Self-clocking loop | `recorder/loop.py` | ✅ |
| Transport | `recorder/net.py` | ✅ DoH + edge rotation |
| Normalisers | `engine/normalize.py` | ✅ liquidations observed |
| Classifier | `engine/signal.py` | ✅ fully cross-sectional |
| Events + scorecard | `engine/events.py` | ✅ grading live |
| Site data generator | `engine/report.py` | ✅ |
| Dashboard | `site/index.html` | ✅ live |
| Tests | `tests/` | ✅ 45, green in CI |

## The scorecard is failing, and that is the finding

As of 20 Sep, on ~1.5 days of data in a single strong uptrend:

| Reading | Horizon | n | Hit | Mean excess |
|---|---|---|---|---|
| loaded_spring | +4h | 12 | **75%** | +4.08% |
| loaded_spring | +24h | 3 | 33% | +0.04% |
| exit_liquidity | +4h | 15 | 33% | +2.36% |
| exit_liquidity | +24h | 17 | 41% | **+7.17%** |
| quiet_accumulation | +4h | 34 | 32% | +0.11% |
| quiet_accumulation | +24h | 31 | 42% | -0.19% |

`exit_liquidity` predicts underperformance and its assets *outperformed by 7%*. It is
currently an inverted signal. `quiet_accumulation` has no edge at all.

**Do not flip the sign to make the table look good.** n is 12–34 per bucket from one
regime; in a bull tape "the crowd arrives late and it keeps going" is just momentum. The
honest position is that the hypothesis is unsupported so far, and saying so is worth more
than a flattering table. Every rival asserts their signal works; this one is measured.

## Not started

Holder growth wired into the classifier · Telegram bot · `FEEDBACK.md` · demo video ·
X post · DoraHacks submission.

## Next, in order

1. **Wire holder growth into the attention axis.** Wallet count rising fast is crowd
   arrival, measured. This replaces the turnover proxy and should be what finally makes
   the readings mean something.
2. **Telegram bot.** The differentiator on "usefulness to a real person": every rival is a
   web app a judge clicks once. Real usage cannot be faked on submission day.
3. **`FEEDBACK.md`** — the material is strong and all of it is measured. See below.
4. Demo video and submission. Leave two clear days.

## Material for FEEDBACK.md, all measured

- Attention and positioning are the two most differentiated datasets and **neither has a
  history endpoint**. `holders/trend/list` is gated while `holders/count` is not.
- **A path that does not exist answers HTTP 200** with `status.error_code` 500, not 404.
  Two controls run on every probe because of it.
- **`/v1/key/info` reports no tier name**, only a credit ceiling. 15,000 means Basic.
- **Naming any `aux` field on `listings/latest` silently drops `platform`**, which is
  where the contract address lives. No error, no warning.
- **`holders/count` takes `platform` and `tokenAddress` in camelCase** where the rest of
  the API is snake_case. Five snake_case spellings returned "Missing required parameter"
  with no hint which one.
- `/v2/cryptocurrency/ohlcv/historical` is gated on Basic but
  `/v3/cryptocurrency/quotes/historical` is not, which is not guessable.
