"use client";

import Link from "next/link";
import { EventRow, READINGS, Reading, Scorecard, useData } from "@/lib/data";
import { AssetLink, Card, Empty, Pill, SectionHead, Skeleton } from "@/components/ui";

const ORDER: Reading[] = ["loaded_spring", "exit_liquidity", "quiet_accumulation", "capitulation"];
const STYLE: Record<string, { text: string; color: string }> = {
  supported: { text: "SUPPORTED", color: "var(--color-good)" },
  rejected: { text: "REJECTED", color: "var(--color-bad)" },
  "no edge": { text: "NO EDGE", color: "var(--ink-3)" },
  "not graded": { text: "NOT GRADED", color: "var(--ink-3)" },
  "too early": { text: "TOO EARLY", color: "var(--ink-3)" },
};

export default function ScorecardPage() {
  const { data, loading } = useData<Scorecard>("scorecard.json");
  const { data: events } = useData<EventRow[]>("events.json");
  const recent = (events ?? []).filter((e) => Object.keys(e.scores ?? {}).length).slice(0, 25);

  return (
    <div className="space-y-8">
      <SectionHead title="Does any of this work?" right={
        data ? <span className="text-xs num" style={{ color: "var(--ink-3)" }}>
          {data.events_total.toLocaleString()} issued · {data.events_graded.toLocaleString()} graded
        </span> : null
      }>
        Every reading is graded against what the price actually did, at +4h, +24h and +72h,
        on <strong style={{ color: "var(--ink)" }}>excess return over the universe median</strong> —
        beating zero in a rising market is not skill. Misses are shown. Only readings made
        on a measured crowd axis are graded: a reading made while the crowd was inferred
        from turnover is a different model, and averaging the two reports the accuracy of
        neither.
      </SectionHead>

      {loading ? <Skeleton rows={4} /> : (
        <div className="grid gap-3 sm:grid-cols-2">
          {ORDER.map((key, i) => {
            const v = data?.verdicts?.[key];
            const s = STYLE[v?.verdict ?? "too early"];
            return (
              <Card key={key} delay={0.05 * i} className="p-5">
                <div className="flex items-center gap-3">
                  <Pill reading={key} />
                  <span className="flex-1" />
                  <span className="rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wider"
                        style={{ color: s.color, borderColor: "currentColor" }}>
                    {s.text}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>
                  {v?.why ?? READINGS[key].blurb}
                </p>
                {v && (
                  <div className="mt-3 flex gap-4 text-[11px] num" style={{ color: "var(--ink-3)" }}>
                    <span>{v.graded_confident} graded on a measured crowd</span>
                    <span>{v.graded_proxied} on the proxy, not graded</span>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <div>
        <SectionHead title="By horizon">
          Mean excess is coloured by whether it <em>supports what the reading claimed</em>,
          not by its sign — a bearish call whose assets rose is a failure, however positive
          the number looks.
        </SectionHead>
        <Card className="overflow-x-auto">
          {!data?.cards?.length ? <Empty>No reading is old enough to grade yet.</Empty> : (
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b hair text-xs" style={{ color: "var(--ink-2)" }}>
                  <th className="px-4 py-2.5 text-left font-medium">Reading</th>
                  <th className="px-4 py-2.5 text-right font-medium">Horizon</th>
                  <th className="px-4 py-2.5 text-right font-medium">Events</th>
                  <th className="px-4 py-2.5 text-right font-medium">Graded</th>
                  <th className="px-4 py-2.5 text-right font-medium">Hit rate</th>
                  <th className="px-4 py-2.5 text-right font-medium">Mean excess</th>
                </tr>
              </thead>
              <tbody>
                {data.cards.map((c, i) => {
                  // Neither supporting nor contradicting below the threshold the verdict
                  // uses — a mean excess of -0.09% is a coin flip, not a finding.
                  const supports = !c.direction || c.material === false
                    ? null : c.mean_excess * c.direction > 0;
                  return (
                    <tr key={i} className="border-b hair last:border-0">
                      <td className="px-4 py-2.5"><Pill reading={c.reading} /></td>
                      <td className="px-4 py-2.5 text-right num">+{c.horizon_h}h</td>
                      <td className="px-4 py-2.5 text-right num">{c.n}</td>
                      <td className="px-4 py-2.5 text-right num">{c.graded}</td>
                      <td className="px-4 py-2.5 text-right num">
                        {c.hit_rate == null ? "not graded" : `${Math.round(c.hit_rate * 100)}%`}
                      </td>
                      <td className="px-4 py-2.5 text-right num"
                          title={supports == null
                            ? (c.direction ? "too small to mean anything" : "")
                            : supports ? "supports the claim" : "contradicts the claim"}
                          style={{ color: supports == null ? "var(--ink-3)"
                                   : supports ? "var(--color-good)" : "var(--color-bad)" }}>
                        {(c.mean_excess * 100 >= 0 ? "+" : "") + (c.mean_excess * 100).toFixed(2)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <div>
        <SectionHead title="Recent graded calls">
          Individual readings and what happened next. Green means it went the way the
          reading claimed, red means it did not.
        </SectionHead>
        <Card className="overflow-x-auto">
          {recent.length === 0 ? <Empty>Nothing graded yet.</Empty> : (
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b hair text-xs" style={{ color: "var(--ink-2)" }}>
                  <th className="px-4 py-2.5 text-left font-medium">Asset</th>
                  <th className="px-4 py-2.5 text-left font-medium">Reading</th>
                  <th className="px-4 py-2.5 text-left font-medium">Opened</th>
                  <th className="px-4 py-2.5 text-right font-medium">+4h</th>
                  <th className="px-4 py-2.5 text-right font-medium">+24h</th>
                  <th className="px-4 py-2.5 text-right font-medium">+72h</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((e, i) => (
                  <tr key={i} className="border-b hair last:border-0 transition hover:bg-[var(--bg-2)]">
                    <td className="px-4 py-2.5 font-medium"><AssetLink symbol={e.symbol} /></td>
                    <td className="px-4 py-2.5"><Pill reading={e.reading} /></td>
                    <td className="px-4 py-2.5 num text-xs" style={{ color: "var(--ink-2)" }}>
                      {new Date(e.opened_at).toUTCString().slice(5, 17)}
                    </td>
                    {["4", "24", "72"].map((h) => {
                      const s = e.scores?.[h];
                      if (!s) return <td key={h} className="px-4 py-2.5 text-right"
                                         style={{ color: "var(--ink-3)" }}>—</td>;
                      return (
                        <td key={h} className="px-4 py-2.5 text-right num"
                            style={{ color: s.hit == null ? "var(--ink-3)"
                                     : s.hit ? "var(--color-good)" : "var(--color-bad)" }}>
                          {(s.excess * 100 >= 0 ? "+" : "") + (s.excess * 100).toFixed(1)}%
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <p className="text-sm" style={{ color: "var(--ink-3)" }}>
        Every grade here comes from one market regime, and the sample is in the tens rather
        than the hundreds. Where the record is not yet enough to say anything, it says
        &ldquo;too early&rdquo; rather than guessing.{" "}
        <Link href="/method" className="underline">How it is measured →</Link>
      </p>
    </div>
  );
}
