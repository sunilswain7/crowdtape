"use client";

import Link from "next/link";
import { Latest, READINGS, Reading, useData, ago } from "@/lib/data";
import { Card, SectionHead } from "@/components/ui";

const ORDER: Reading[] = ["loaded_spring", "exit_liquidity", "quiet_accumulation", "capitulation"];

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold"
           style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>{n}</div>
      <div>
        <h3 className="font-semibold">{title}</h3>
        <div className="mt-1.5 text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>{children}</div>
      </div>
    </div>
  );
}

export default function Method() {
  const { data } = useData<Latest>("latest.json");

  return (
    <div className="max-w-3xl space-y-10">
      <SectionHead title="How this works">
        No part of this is a secret, and every number on the board regenerates from the
        recorded snapshots in the repository with one command.
      </SectionHead>

      <Card className="space-y-6 p-6">
        <Step n={1} title="Record what CoinMarketCap throws away">
          CoinMarketCap knows which coins people look up before they buy — it is where they
          look them up. That is one endpoint, <code>trending/most-visited</code>, and there
          is no history for it. Same for liquidations and open interest: latest-only,
          generated and discarded. So a recorder takes a snapshot every ten minutes and
          commits it.{" "}
          {data && (
            <strong style={{ color: "var(--ink)" }}>
              {data.snapshots_recorded.toLocaleString()} snapshots so far, since{" "}
              {new Date(data.first_recorded).toUTCString().slice(5, 16)}.
            </strong>
          )}{" "}
          The git history <em>is</em> the dataset: every snapshot is a commit, timestamped
          by GitHub, independently verifiable.
        </Step>

        <Step n={2} title="Read three axes, all relative">
          Nothing is judged against a fixed number. The first run against live data called
          126 of 200 assets a signal, because the market was up 4.2% that day and the test
          was &ldquo;up more than 2%&rdquo; — beta with a label on it. Price is judged on
          its excess over the universe median; liquidation stress on its rank within the
          universe; attention on position in the most-visited list and how that position
          is moving.
        </Step>

        <Step n={3} title="Measure the crowd, do not infer it">
          The crowd axis prefers a count of people over a proxy for them: position on the
          most-visited list first, then wallet growth — how fast the number of distinct
          holders is changing — and only then turnover. A reading resting on turnover is
          marked <em>unconfirmed</em> everywhere it appears and is never graded.
        </Step>

        <Step n={4} title="Grade every call, publish the failures">
          Each reading is scored at +4h, +24h and +72h against the median forward return of
          the universe — not against zero, because a call that gained 5% on a day the
          market gained 6% lagged a coin picked at random. Readings that claim no direction
          take no credit. <Link href="/scorecard" className="underline">The scorecard</Link>{" "}
          says plainly where the record does not support the claim.
        </Step>
      </Card>

      <div>
        <SectionHead title="The four readings">
          Each is a hypothesis about what a crowd arriving at a particular moment means.
          The scorecard is what decides whether it is true.
        </SectionHead>
        <div className="grid gap-3 sm:grid-cols-2">
          {ORDER.map((k, i) => (
            <Card key={k} delay={0.05 * i} className="p-4">
              <div className="flex items-center gap-2 font-medium">
                <i className="size-2 rounded-full" style={{ background: READINGS[k].color }} />
                {READINGS[k].label}
              </div>
              <p className="mt-2 text-[13px] leading-relaxed" style={{ color: "var(--ink-2)" }}>
                {READINGS[k].blurb}
              </p>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <SectionHead title="What it does not do">
          The limits, stated rather than buried.
        </SectionHead>
        <Card className="p-5">
          <ul className="space-y-3 text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>
            <li>
              <strong style={{ color: "var(--ink)" }}>The record is young.</strong> Grades on
              a measured crowd axis number in the tens, not the hundreds, and all of them
              come from a single market regime. A signal that works in an uptrend has not
              been tested.
            </li>
            <li>
              <strong style={{ color: "var(--ink)" }}>Attention was gated at first.</strong>{" "}
              The most-visited feed was not available on this API plan until 21 September.
              Readings before that rest on turnover, are marked unconfirmed, and are excluded
              from grading.
            </li>
            <li>
              <strong style={{ color: "var(--ink)" }}>Wallet counts are partial.</strong> Only
              assets with a contract address CoinMarketCap&rsquo;s DEX index reaches
              {data?.wallets_covered ? ` — ${data.wallets_covered} of ${data.universe} right now` : ""}.
            </li>
            <li>
              <strong style={{ color: "var(--ink)" }}>It is not advice.</strong> It is a
              measurement of what other people are looking at, and a public record of how
              often that measurement has been wrong.
            </li>
          </ul>
        </Card>
      </div>

      <div>
        <SectionHead title="Endpoints used">
          Measured against a live key, not read from documentation.
        </SectionHead>
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <tbody>
              {[
                ["/v1/cryptocurrency/trending/most-visited", "the crowd axis — 24h, 7d and 30d"],
                ["/v1/cryptocurrency/listings/latest", "the market-cap universe, price, tags, contracts"],
                ["/v5/derivatives/liquidations/cryptocurrency/list/latest", "long and short liquidations at 1h, 4h, 24h"],
                ["/v5/exchange/derivatives/list", "open interest and derivative volume by venue"],
                ["/v1/dex/holders/count", "distinct wallets holding a token"],
                ["/v1/cryptocurrency/trending/latest", "corroborating attention"],
                ["/v1/global-metrics/quotes/latest", "total cap, dominance, derivative volume"],
                ["/v3/fear-and-greed/latest", "sentiment, for context"],
                ["/v1/key/info", "credit budget, and the only way to infer the plan"],
              ].map(([p, w]) => (
                <tr key={p} className="border-b hair last:border-0">
                  <td className="px-4 py-2.5 font-mono text-[12px]" style={{ color: "var(--ink)" }}>{p}</td>
                  <td className="px-4 py-2.5 text-[13px]" style={{ color: "var(--ink-2)" }}>{w}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <p className="mt-3 text-sm" style={{ color: "var(--ink-3)" }}>
          Where the API got in the way is written up in{" "}
          <a className="underline" href="https://github.com/sunilswain7/crowdtape/blob/main/FEEDBACK.md">
            FEEDBACK.md
          </a>{" "}— eight findings, every one measured, with the reproduction for each.
        </p>
      </div>
    </div>
  );
}
