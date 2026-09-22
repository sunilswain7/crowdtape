# Crowdtape

**The tape is what happened. The crowd is what happens next.**

Built for the [Build with CMC: API Hackathon](https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail).
Track: **Markets and Trading Tools**.

**[Live board](https://sunilswain7.github.io/crowdtape/)** ·
**[@crowdtape_bot](https://t.me/crowdtape_bot)** on Telegram ·
**[JUDGE.md](JUDGE.md)** if you have sixty seconds

---

## The problem

CoinMarketCap is where a few hundred million people a month go to look a coin up
*before* they buy it. The API exposes that as `trending/most-visited` — a live feed of
retail lookup intent, and the one dataset in crypto that no competing data provider can
sell you. Social tools like LunarCrush measure what people *post*. This measures what
they *privately research right before they act*.

CoinMarketCap throws it away. There is no history endpoint for attention. The same is
true of positioning: `/v5/` carries per-asset open interest, funding rate and long/short
liquidations, and none of it is retained either. Both are latest-only. Ask what the crowd
was looking at last Tuesday and nothing, anywhere, can answer — including CoinMarketCap.

So the first thing this repo does is start writing it down.

## What it answers

One question, asked per asset, every few minutes: **is the crowd arriving early, or are
you their exit liquidity?**

| Attention | Leverage | Price | Reading |
|---|---|---|---|
| spiking | open interest building | flat | **Loaded spring** — crowd arriving, leverage stacking, no move yet |
| spiking | funding hot | up | **Exit liquidity** — late retail into crowded longs |
| flat | flat | up | **Quiet accumulation** — spot-led, healthiest move on the board |
| spiking | longs liquidating | down | **Capitulation** |

Every transition between quadrants emits a timestamped event. Every event is then graded
at +4h, +24h and +72h against what the price actually did, and the hit rate is published
**including the misses**. A signal nobody scores is a claim, not a tool.

## Status

Early. This README describes what is built, not what is planned — the sections below grow
as the work lands.

| Piece | State |
|---|---|
| Capability probe (`scripts/probe.py`) | ✅ built |
| Snapshot recorder (`recorder/record.py`) | ✅ built |
| Scheduled recording (GitHub Actions, 15 min) | ✅ built |
| Signal engine (`engine/`) | ✅ built |
| Event detection + scorecard | ✅ built |
| Site data generator (`engine/report.py`) | ✅ built |
| Dashboard (`site/`) | ✅ [live](https://sunilswain7.github.io/crowdtape/) |
| Telegram bot (`bot/`) | ✅ built |
| Test suite | ✅ 38 tests, green in CI |
| Telegram bot | not started |
| MCP tool | not started |

## How the engine is built

Three axes - price, attention, leverage - each reduced to a state, then combined into one
reading. The thresholds are constants at the top of [`engine/signal.py`](engine/signal.py)
rather than buried in the logic, because a heuristic nobody can see is a heuristic nobody
can argue with, and every one of them is a judgement call that deserves arguing with.

Every field name CoinMarketCap chose lives in [`engine/normalize.py`](engine/normalize.py)
and nowhere else. The classifier reads canonical records, so it needs no key, no network
and no recorded data to test - and when a payload turns out to differ from what was
assumed, one function changes and the logic and its tests are untouched.

```bash
python3 -m unittest discover -s tests -t . -v      # 38 tests, no key required
```

## How the scorecard is honest

A reading on its own is a claim. [`engine/events.py`](engine/events.py) turns readings
into dated, immutable events and grades them against what the price actually did.

Two choices there are worth defending:

**Excess return, not raw return.** An event is scored against the median forward return
of the universe at the same instant, not against zero. A "loaded spring" that gained 5%
on a day the whole market gained 6% did not find anything — it lagged a coin picked at
random. Raw returns flatter every reading in a rising market and damn every reading in a
falling one, which is how a scorecard turns into a marketing asset instead of a
measurement.

**Readings that predict nothing are not graded.** `capitulation` is directionally
ambiguous, so it carries no direction and takes no credit — but it still appears in the
report with its count, so it cannot quietly vanish for being inconvenient.

Events also have to hold for two consecutive snapshots before they open, because an asset
sitting on a threshold otherwise flaps between readings and manufactures a dozen events
out of one situation. There is a test for that.

**What the engine will not do is pretend.** When the attention stream is plan-gated, the
classifier falls back to turnover - volume against market cap - as a proxy for unusual
interest, and marks the verdict `confident=False`, because a proxy is not the same
measurement. When an axis is missing entirely it reads `unknown` rather than a default.
A gated stream is recorded as a 403 in the snapshot, not silently dropped.

## The bot

The dashboard is a page a judge opens once. The bot is the same readings in the place
someone actually checks the market from.

It **never calls CoinMarketCap.** It reads the JSON the recorder already publishes, so it
holds no API key, spends no credits, and cannot drift from the board — if the site says a
thing, so does the bot, because it is the same file.

Talk to it: **[@crowdtape_bot](https://t.me/crowdtape_bot)**

```
/board   what is carrying a reading right now
/coin    one asset in full, with its wallet count
/score   whether these readings actually work
/why     what the four readings mean
```

`/score` is the one that matters. It reports that one of the four readings is currently
**rejected** by its own record, and `/coin` repeats that warning wherever that reading
appears. A bot that quietly dropped the qualifier would be a more confident product and a
less truthful one; there are tests pinning it.

Usage is logged as a **hash of the chat id**, never the id itself, so the count of real
people using it can be reported without publishing who they are.

## The dataset is the git history

`recorder/record.py` appends one snapshot per run to `data/YYYY-MM-DD.jsonl`, and the
workflow commits it. Every snapshot is therefore a commit, timestamped by GitHub,
publicly auditable and independently verifiable. No database is needed to start, and the
commit log doubles as evidence of continuous real API calls rather than a single
screenshotted `curl`.

```bash
CMC_API_KEY=your-key python3 recorder/record.py
```

## Endpoints used

| Endpoint | Axis | Plan |
|---|---|---|
| `GET /v1/cryptocurrency/trending/most-visited` | attention | Startup |
| `GET /v1/cryptocurrency/trending/latest` | attention | Startup |
| `GET /v5/derivatives/liquidations/cryptocurrency/list/latest` | positioning | Basic |
| `GET /v5/exchange/derivatives/list` | positioning | Basic |
| `GET /v1/cryptocurrency/listings/latest` | price | Basic |
| `GET /v1/global-metrics/quotes/latest` | context | Basic |
| `GET /v3/fear-and-greed/latest` | context | Basic |
| `GET /v1/key/info` | metering | Basic |

### Running the probe

Run it from the **Actions tab** (`probe` workflow), not locally. The machine this was
built on sits behind an ISP that hijacks DNS for `coinmarketcap.com` *and* injects TCP
resets keyed on the TLS SNI for `pro-api` - measured at 2 successful calls in 16, spread
evenly across all four CloudFront edges, so neither a DNS fix nor edge pinning solves it.
`recorder/net.py` resolves over DoH and rotates edges, which makes a local call *possible*
but not *reliable*. CI has neither problem. This is the reason the recorder is a scheduled
workflow rather than something running on a laptop.

Access is **measured, not assumed**. `/v1/key/info` returns no tier name, only a credit
ceiling — 15,000 means Basic, 450,000 means Startup — so `scripts/probe.py` asks the live
API what this key may actually reach and records the answer.

```bash
CMC_API_KEY=your-key python3 scripts/probe.py
```

The probe encodes one trap worth stating plainly: **a path that does not exist on
`pro-api.coinmarketcap.com` returns HTTP 200**, with `status.error_code` 500 and "The
system is busy, please try again later!". Reading the HTTP status alone records imaginary
endpoints as working. Two known-fake control paths run on every invocation, and a run
where the controls misbehave is reported as untrustworthy rather than quietly wrong.

*Credit for that finding goes to [geralexgr/coinmarketcap-divergence](https://github.com/geralexgr/coinmarketcap-divergence),
a fellow entrant who documented it after losing two days to it.*

## Not committed here

The API key. `.env` is gitignored and `.env.example` shows the shape. The hackathon rules
are explicit that a committed key counts against code quality.

## Where the API got in the way

[`FEEDBACK.md`](FEEDBACK.md) — eight findings, all measured against a live key rather than
read from documentation, with the reproduction for each. The short version: the two
datasets CoinMarketCap has that nobody else does are the two it does not retain, a path
that does not exist answers HTTP 200, and naming any `aux` field silently drops
`platform`.

## Licence

MIT.
