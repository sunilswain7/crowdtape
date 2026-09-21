# What the API made possible, and where it got in the way

Everything below was measured against a live key between 18 and 21 September 2026, not
read from the documentation. The measurements are reproducible: `scripts/probe.py`
regenerates [`docs/endpoint-access.md`](docs/endpoint-access.md) and
[`docs/payload-shapes.md`](docs/payload-shapes.md) from the live API on every run, and
publishes what it found, including the failures.

---

## What it made possible

**The `/v5` derivatives family is the best-kept secret in this API.** Long and short
liquidations for 100 assets, split at 1h/4h/24h, for **one credit** — and it is callable
on the free Basic plan. Nothing else we found gives per-asset forced-deleveraging data at
that price. It became an entire axis of this project.

**`/v1/dex/holders/count` is a genuinely unusual dataset.** A count of distinct wallets
holding a token is a measurement of a crowd rather than a proxy for one. When the
attention endpoints turned out to be gated, this is what replaced them, and it is a
better signal than the turnover we would otherwise have used.

**The error messages are often excellent.** `/v5/cryptocurrency/derivatives/market-pairs`
answers a bad request with `'value' must contain at least one of [crypto_id,
crypto_symbol, crypto_slug]`. That single line replaced a documentation lookup. More of
this, please — see §6 for the counter-example.

---

## 1. Your two most differentiated datasets have no history endpoint

Attention (`trending/most-visited`) and positioning (liquidations, open interest) are the
things this API has that a dozen competitors do not. Price is a commodity; *what 300
million people looked up yesterday* is not.

Neither is retained. There is no `trending/historical`, no liquidations history, no
open-interest history. The data is generated, served once, and discarded.

So the first thing this project built was a recorder, and the reason it exists at all is
that **the interesting question is always "compared to what?"** — and the API can only
ever answer "right now". As of writing we hold 272 snapshots at ten-minute spacing of a
series that does not exist anywhere else, including, as far as we can tell, at
CoinMarketCap.

**The ask:** a historical endpoint for trending and for liquidations, even at daily
granularity, even Enterprise-only. It is the highest-value thing you could ship.

## 2. A path that does not exist answers HTTP 200

```
GET /v3/totally-made-up/xyz    →  200 OK
{"status": {"error_code": 500,
            "error_message": "The system is busy, please try again later!"}}
```

Not 404. Reading the HTTP status alone records imaginary endpoints as working. A fellow
entrant lost two days to this — they swept `/v1` to `/v4` for the derivatives family,
concluded from the 200s that it did not exist, and published that conclusion before
discovering it lives under `/v5`.

Every probe in this repo now runs two known-fake control paths and refuses to trust a run
where they misbehave. That should not be necessary.

**The ask:** 404 for a path that does not exist.

## 3. `/v1/key/info` does not report the plan's name

It returns `credit_limit_monthly` and `rate_limit_minute`, and no tier name. The only way
to know which plan a key is on is to recognise the number — 15,000 means Basic, 450,000
means Startup. Our probe hardcodes that mapping, which will rot the moment pricing
changes.

This mattered more than it should have: a hackathon upgrade was promised within 24 hours
of registration and never arrived, and the only way to check was to read a credit ceiling
and infer. **The ask:** a `plan.name` field.

## 4. Naming any `aux` field silently drops `platform`

```
listings/latest?limit=20                       → 8 of 20 carry platform.token_address
listings/latest?limit=20&aux=cmc_rank,tags     → 0 of 20
listings/latest?limit=20&aux=cmc_rank,tags,platform → 8 of 20
```

`platform` is where the contract address lives. Asking for two unrelated auxiliary fields
removes it, with no error and no warning — the response is a valid 200 with a quietly
smaller shape. We added `aux=cmc_rank,tags` for the `tags` field, did not notice
`platform` vanish, and shipped a holder-count pass that silently found zero tokens.

`tags` is returned with or without `aux`, so the parameter did nothing except break
something else.

**The ask:** treat `aux` as additive, or document that it is exclusive and list the
defaults it displaces.

## 5. `holders/count` is open, `holders/trend/list` is gated

```
/v1/dex/holders/count       → 200 on Basic
/v1/dex/holders/trend/list  → 403 on Basic
```

We understand the commercial logic. It is worth knowing what it produces: we poll the
count every three hours and compute the trend ourselves. The gate does not protect the
derived data, it just moves the work — and the version we compute is one nobody can audit
against yours.

## 6. `holders/count` takes camelCase in a snake_case API

The working parameters are `platform` and `tokenAddress`. Every other endpoint we touched
uses snake_case, so we tried `contract_address`, `token_address`, `address`,
`base_asset_contract_address` — ten spellings across two rounds — and each returned:

```
{"error_message": "Missing required parameter."}
```

Which parameter? The message does not say, and the documentation is
[behind a page](https://coinmarketcap.com/api/documentation/v1/) our network could not
reach. We eventually found the answer in **another hackathon entrant's public source
code**, then verified it live.

**Two asks:** make the naming consistent, and name the missing parameter in the error.
§ "What it made possible" shows you already do this well elsewhere.

## 7. Plan boundaries are not guessable

```
/v2/cryptocurrency/ohlcv/historical   → 403 on Basic
/v3/cryptocurrency/quotes/historical  → 200 on Basic
/v1/cryptocurrency/listings/historical → 200 on Basic
/v1/cryptocurrency/listings/new       → 403 on Basic
```

Two historical endpoints, one gated and one not. `listings/latest` open, `listings/new`
gated. The pricing page's feature rows do not map onto endpoint paths closely enough to
predict any of this, and a widely-used third-party summary of the tiers was wrong in both
directions. We planned three days of work around it before measuring.

**The ask:** publish the plan gate per endpoint path in the reference docs, or expose it
on `/v1/key/info`.

## 8. A note on the rate limit and the Basic ceiling

50 requests/minute on Basic is generous for interactive use and awkward for a recorder:
our holder pass sleeps 1.3s between calls to stay under it, which makes a 50-token pass
take a minute. The 15,000/month ceiling is the real constraint — it forced the whole
sampling design (10-minute snapshots, 3-hourly holder passes), which is a reasonable
thing for a free tier to do, and we mention it only to note that *credits, not rate,* is
what shapes what gets built.

---

## Endpoints used

| Endpoint | What for |
|---|---|
| `GET /v1/cryptocurrency/listings/latest` | the 200-asset universe, price, volume, tags, contract addresses |
| `GET /v5/derivatives/liquidations/cryptocurrency/list/latest` | long/short liquidations at 1h, 4h, 24h |
| `GET /v5/exchange/derivatives/list` | open interest and derivative volume by venue |
| `GET /v1/dex/holders/count` | distinct wallets holding a token — the crowd axis |
| `GET /v1/global-metrics/quotes/latest` | total cap, dominance, derivative volume |
| `GET /v3/fear-and-greed/latest` | sentiment, for context |
| `GET /v1/key/info` | credit budget, and the only way to infer the plan |
| `GET /v1/cryptocurrency/trending/most-visited` | **intended crowd axis — 403 on every call** |

The last row is the honest one. This project was designed around lookup intent, the one
dataset in crypto that only CoinMarketCap has. The hackathon's free Startup tier never
reached our key, so the code that reads it is written, tested, and has never once run
against a 200. It will start producing without a code change the moment the plan allows.
