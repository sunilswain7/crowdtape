"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Latest, Scorecard, READINGS, useData, ago, money, pct,
} from "@/lib/data";
import {
  AssetLink, AttentionCell, Card, Empty, Pill, SectionHead, Signed, Skeleton, Stat, fadeUp,
} from "@/components/ui";
import Spark from "@/components/Spark";
import Gauge from "@/components/Gauge";

const VERDICT_STYLE: Record<string, { text: string; color: string }> = {
  supported: { text: "SUPPORTED", color: "var(--color-good)" },
  rejected: { text: "REJECTED", color: "var(--color-bad)" },
  "no edge": { text: "NO EDGE", color: "var(--ink-3)" },
  "not graded": { text: "NOT GRADED", color: "var(--ink-3)" },
  "too early": { text: "TOO EARLY", color: "var(--ink-3)" },
};

export default function Overview() {
  const { data: latest, loading } = useData<Latest>("latest.json");
  const { data: score } = useData<Scorecard>("scorecard.json");

  const rows = latest?.rows ?? [];
  const gaps = rows.filter((r) => r.attention_over_cap).sort(
    (a, b) => (b.attention_over_cap ?? 0) - (a.attention_over_cap ?? 0));
  const flagged = rows.filter((r) => r.reading !== "nothing");
  const widest = gaps[0];
  const counts: Record<string, number> = {};
  for (const r of flagged) counts[r.reading] = (counts[r.reading] ?? 0) + 1;

  return (
    <div className="space-y-12">
      {/* --- the claim, stated once, at the top --------------------------- */}
      <motion.section {...fadeUp} className="relative pt-4">
        <div className="pointer-events-none absolute -inset-x-20 -top-24 h-72 -z-10"
             style={{ background: "var(--glow)" }} />
        <p className="text-sm font-medium" style={{ color: "var(--accent)" }}>
          {latest ? `${latest.snapshots_recorded.toLocaleString()} snapshots · updated ${ago(latest.at)}`
                  : " "}
        </p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-semibold tracking-tight leading-[1.08] max-w-4xl">
          The tape is what happened.
          <br />
          <span className="grad">The crowd is what happens next.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-relaxed" style={{ color: "var(--ink-2)" }}>
          CoinMarketCap knows which coins people are looking up before they buy — and keeps
          no history of it. This records it every ten minutes, reads it against price and
          leverage, and grades every call it makes.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/board"
            className="rounded-lg px-4 py-2 text-sm font-medium transition hover:opacity-90"
            style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-2))",
                     color: "#fff", boxShadow: "0 8px 24px -10px var(--accent)" }}
          >
            Open the board
          </Link>
          <Link
            href="/scorecard"
            className="rounded-lg border hair px-4 py-2 text-sm font-medium transition hover:bg-[var(--bg-2)]"
          >
            Does it work?
          </Link>
        </div>
      </motion.section>

      {/* --- the headline number ------------------------------------------ */}
      {widest && (
        <motion.section {...fadeUp}>
          <Card className="overflow-hidden">
            <div className="grid gap-6 p-6 sm:p-8 md:grid-cols-[1.1fr_1fr] md:items-center">
              <div>
                <div className="text-xs uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
                  Widest attention gap right now
                </div>
                <div className="mt-2 flex items-baseline gap-3">
                  <AssetLink symbol={widest.symbol}>
                    <span className="text-3xl font-semibold tracking-tight">{widest.symbol}</span>
                  </AssetLink>
                  <span className="text-3xl font-semibold num" style={{ color: "var(--accent)" }}>
                    {Math.round(widest.attention_over_cap ?? 0)}×
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>
                  The <strong style={{ color: "var(--ink)" }}>#{widest.attention_rank}</strong> most
                  looked-up asset on CoinMarketCap, ranked{" "}
                  <strong style={{ color: "var(--ink)" }}>#{widest.rank}</strong> by market cap.
                  A top-200 screener cannot see it at all.
                </p>

                <dl className="mt-5 grid max-w-sm grid-cols-3 gap-4 border-t pt-4 hair">
                  {[
                    { k: "24h", v: <Signed v={widest.pct_24h} dp={1} /> },
                    { k: "vs market", v: <Signed v={widest.pct_24h == null || latest?.median_move_24h == null
                        ? null : widest.pct_24h - latest.median_move_24h} dp={1} /> },
                    { k: "Market cap", v: money(widest.market_cap) },
                  ].map((s) => (
                    <div key={s.k}>
                      <dt className="text-[11px]" style={{ color: "var(--ink-3)" }}>{s.k}</dt>
                      <dd className="mt-0.5 text-base font-semibold num">{s.v}</dd>
                    </div>
                  ))}
                </dl>

                {widest.reading !== "nothing" && (
                  <div className="mt-4 flex items-start gap-2.5">
                    <Pill reading={widest.reading} />
                    <span className="text-[13px]" style={{ color: "var(--ink-2)" }}>
                      {widest.why}
                    </span>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                {gaps.slice(0, 5).map((r, i) => (
                  <motion.div
                    key={r.id}
                    {...fadeUp}
                    transition={{ ...fadeUp.transition, delay: 0.05 * i }}
                    className="flex items-center gap-3 rounded-lg px-3 py-2"
                    style={{ background: "var(--bg-2)" }}
                  >
                    <span className="num text-xs w-10 shrink-0" style={{ color: "var(--ink-3)" }}>
                      #{r.attention_rank}
                    </span>
                    <AssetLink symbol={r.symbol}>
                      <span className="font-medium">{r.symbol}</span>
                    </AssetLink>
                    <span className="num text-xs" style={{ color: "var(--ink-3)" }}>
                      cap #{r.rank}
                    </span>
                    <span className="flex-1" />
                    <span className="num text-sm font-semibold" style={{ color: "var(--accent)" }}>
                      {Math.round(r.attention_over_cap ?? 0)}×
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          </Card>
        </motion.section>
      )}

      {/* --- market ------------------------------------------------------- */}
      <section>
        <SectionHead title="Market">
          {latest
            ? `${latest.universe} assets — the market-cap top 200 plus every asset on the
               most-visited list, because the interesting ones are rarely in both.`
            : ""}
        </SectionHead>
        <div className="grid gap-3 lg:grid-cols-3">
          <Card className="p-5 panel-hover lg:col-span-2">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-xs" style={{ color: "var(--ink-2)" }}>Total market cap</div>
                <div className="mt-1 text-3xl font-semibold num">
                  {money(latest?.market?.market_cap)}
                </div>
                <div className="mt-1 text-xs num" style={{ color: "var(--ink-3)" }}>
                  24h volume {money(latest?.market?.volume_24h)} · BTC dominance{" "}
                  {latest?.market?.btc_dominance?.toFixed(1) ?? "—"}%
                </div>
              </div>
              <Spark w={230} h={54}
                     values={(latest?.market_series ?? []).map((p) => p.market_cap)} />
            </div>
            <div className="mt-5 grid grid-cols-2 gap-4 border-t pt-4 hair sm:grid-cols-4">
              {[
                { k: "Median 24h", v: pct(latest?.median_move_24h ?? null),
                  c: (latest?.median_move_24h ?? 0) >= 0 ? "var(--color-good)" : "var(--color-bad)" },
                { k: "Open interest", v: money(latest?.market?.open_interest) },
                { k: "Attention measured", v: latest?.attention_covered ?? "—" },
                { k: "Wallets tracked", v: latest?.wallets_covered ?? "—" },
              ].map((x) => (
                <div key={x.k}>
                  <div className="text-[11px]" style={{ color: "var(--ink-3)" }}>{x.k}</div>
                  <div className="mt-0.5 text-base font-semibold num" style={{ color: x.c }}>
                    {x.v}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="flex flex-col justify-between gap-4 p-5 panel-hover" delay={0.06}>
            <Gauge value={latest?.market?.fear_greed ?? null}
                   label={latest?.market?.fear_greed_label ?? "Fear & Greed"} />
            <div className="border-t pt-4 hair">
              <div className="text-xs" style={{ color: "var(--ink-2)" }}>Carrying a reading</div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-semibold num">{latest ? flagged.length : "—"}</span>
                <span className="text-xs" style={{ color: "var(--ink-3)" }}>
                  of {latest?.universe ?? "—"} assets
                </span>
              </div>
              <div className="mt-2 flex h-1.5 overflow-hidden rounded-full"
                   style={{ background: "var(--bg-3)" }}>
                {(["exit_liquidity","loaded_spring","capitulation","quiet_accumulation"] as const)
                  .map((k) => {
                    const n = counts[k] ?? 0;
                    const w = latest ? (n / Math.max(1, flagged.length)) * 100 : 0;
                    return <div key={k} style={{ width: `${w}%`, background: READINGS[k].color }} />;
                  })}
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* --- the honest bit ------------------------------------------------ */}
      <section>
        <SectionHead title="What the record says" right={
          <Link href="/scorecard" className="text-sm hover:underline" style={{ color: "var(--accent)" }}>
            Full scorecard →
          </Link>
        }>
          Every reading is graded against what the price actually did, on excess return over
          the market median. Beating zero in a rising market is not skill.
        </SectionHead>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(["loaded_spring", "exit_liquidity", "quiet_accumulation", "capitulation"] as const).map(
            (key, i) => {
              const v = score?.verdicts?.[key];
              const style = VERDICT_STYLE[v?.verdict ?? "too early"];
              return (
                <Card key={key} delay={0.05 * i} className="p-4">
                  <div className="flex items-center gap-2">
                    <Pill reading={key} />
                    <span className="flex-1" />
                    <span
                      className="rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wider"
                      style={{ color: style.color, borderColor: "currentColor" }}
                    >
                      {style.text}
                    </span>
                  </div>
                  <p className="mt-2 text-[13px] leading-relaxed" style={{ color: "var(--ink-2)" }}>
                    {v?.why ?? READINGS[key].blurb}
                  </p>
                </Card>
              );
            })}
        </div>
      </section>

      {/* --- live board preview -------------------------------------------- */}
      <section>
        <SectionHead title="Live now" right={
          <Link href="/board" className="text-sm hover:underline" style={{ color: "var(--accent)" }}>
            Full board →
          </Link>
        }>
          The assets carrying a reading this minute, ordered by how looked-at they are.
        </SectionHead>
        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-4"><Skeleton rows={6} /></div>
          ) : flagged.length === 0 ? (
            <Empty>Nothing is carrying a reading. That is a real answer, not a missing one.</Empty>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b hair text-xs" style={{ color: "var(--ink-2)" }}>
                  <th className="px-4 py-2.5 text-left font-medium">Looked up</th>
                  <th className="px-4 py-2.5 text-left font-medium">Asset</th>
                  <th className="px-4 py-2.5 text-left font-medium">Reading</th>
                  <th className="px-4 py-2.5 text-right font-medium">24h</th>
                  <th className="hidden sm:table-cell px-4 py-2.5 text-right font-medium">vs market</th>
                </tr>
              </thead>
              <tbody>
                {flagged.slice(0, 8).map((r) => (
                  <tr key={r.id} className="border-b hair last:border-0 transition hover:bg-[var(--bg-2)]">
                    <td className="px-4 py-2.5">
                      <AttentionCell rank={r.attention_rank} cap={r.rank} gap={r.attention_over_cap} />
                    </td>
                    <td className="px-4 py-2.5 font-medium"><AssetLink symbol={r.symbol} /></td>
                    <td className="px-4 py-2.5"><Pill reading={r.reading} /></td>
                    <td className="px-4 py-2.5 text-right num"><Signed v={r.pct_24h} dp={1} /></td>
                    <td className="hidden sm:table-cell px-4 py-2.5 text-right num">
                      <Signed v={r.pct_24h == null || latest?.median_move_24h == null
                        ? null : r.pct_24h - latest.median_move_24h} dp={1} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </section>
    </div>
  );
}
