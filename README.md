# Crowdtape

**The tape is what happened. The crowd is what happens next.**

Built for the [Build with CMC: API Hackathon](https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail).
Track: **Markets and Trading Tools**.

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
| Signal engine | in progress |
| Event scorecard | not started |
| Web app | not started |
| Telegram bot | not started |
| MCP tool | not started |

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

## Licence

MIT.
