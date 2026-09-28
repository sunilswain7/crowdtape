"use client";

import Link from "next/link";
import { Latest, money, pct } from "@/lib/data";

/**
 * The strip along the bottom.
 *
 * Every market terminal has one, and it earns its place here: the board's subject is a
 * gap between attention and size, and that gap only means something against the state of
 * the tape. It duplicates in one line what would otherwise cost a scroll.
 */
export default function Ticker({ latest }: { latest: Latest | null }) {
  if (!latest) return null;
  const m = latest.market ?? {};
  const flagged = latest.rows.filter((r) => r.reading !== "nothing").length;
  const gaps = latest.rows
    .filter((r) => r.attention_over_cap && r.attention_over_cap >= 2)
    .sort((a, b) => (b.attention_over_cap ?? 0) - (a.attention_over_cap ?? 0))
    .slice(0, 8);

  const stats: [string, React.ReactNode][] = [
    ["Market cap", money(m.market_cap)],
    ["24h vol", money(m.volume_24h)],
    ["BTC dom", m.btc_dominance ? `${m.btc_dominance.toFixed(1)}%` : "—"],
    ["Open interest", money(m.open_interest)],
    ["Fear & Greed", m.fear_greed != null ? `${m.fear_greed} ${m.fear_greed_label ?? ""}` : "—"],
    ["Median 24h", <Signed key="m" v={latest.median_move_24h} />],
    ["Flagged", `${flagged} of ${latest.universe}`],
  ];

  const run = (
    <div className="flex shrink-0 items-center gap-6 pr-6">
      {stats.map(([k, v]) => (
        <span key={k} className="whitespace-nowrap">
          <span style={{ color: "var(--ink-3)" }}>{k} </span>
          <span className="num font-medium">{v}</span>
        </span>
      ))}
      {gaps.map((g) => (
        <Link key={g.id} href={`/asset/?s=${g.symbol}`}
              className="whitespace-nowrap hover:underline">
          <span className="font-medium">{g.symbol}</span>
          <span className="num" style={{ color: "var(--accent)" }}>
            {" "}#{g.attention_rank} · {Math.round(g.attention_over_cap ?? 0)}×
          </span>
        </Link>
      ))}
    </div>
  );

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 h-[34px] overflow-hidden border-t hair text-[12px] backdrop-blur-xl"
      style={{ background: "color-mix(in oklab, var(--bg-1) 88%, transparent)" }}
    >
      <div className="flex h-full items-center">
        <div className="flex marquee">
          {run}
          {run}
        </div>
      </div>
    </div>
  );
}

function Signed({ v }: { v: number | null | undefined }) {
  if (v == null) return <>—</>;
  return <span style={{ color: v >= 0 ? "var(--color-good)" : "var(--color-bad)" }}>{pct(v, 2)}</span>;
}
