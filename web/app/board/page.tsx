"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Latest, READINGS, Reading, useData, ago, money, price } from "@/lib/data";
import {
  AssetLink, AttentionCell, Card, Empty, Pill, SectionHead, Signed, Skeleton,
} from "@/components/ui";

type SortKey = "attention" | "cap" | "move" | "excess" | "wallets";
const FILTERS: (Reading | "all")[] =
  ["all", "loaded_spring", "exit_liquidity", "quiet_accumulation", "capitulation"];

export default function Board() {
  const { data, loading } = useData<Latest>("latest.json");
  const [filter, setFilter] = useState<Reading | "all">("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("attention");
  const [showAll, setShowAll] = useState(false);

  const median = data?.median_move_24h ?? 0;

  const rows = useMemo(() => {
    let r = (data?.rows ?? []).filter((x) => showAll || x.reading !== "nothing");
    if (filter !== "all") r = r.filter((x) => x.reading === filter);
    if (q.trim()) {
      const needle = q.trim().toUpperCase().replace(/^\$/, "");
      r = r.filter((x) => x.symbol.includes(needle));
    }
    const excess = (x: typeof r[number]) => (x.pct_24h == null ? -1e9 : x.pct_24h - median);
    const by: Record<SortKey, (a: typeof r[number], b: typeof r[number]) => number> = {
      // Attention first: it is the subject, and ordering by market cap buries the rows
      // that make the point — the most looked-at asset is routinely a tiny one.
      attention: (a, b) => (a.attention_rank ?? 1e9) - (b.attention_rank ?? 1e9),
      cap: (a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9),
      move: (a, b) => (b.pct_24h ?? -1e9) - (a.pct_24h ?? -1e9),
      excess: (a, b) => excess(b) - excess(a),
      wallets: (a, b) => (b.wallet_count ?? -1) - (a.wallet_count ?? -1),
    };
    return [...r].sort(by[sort]);
  }, [data, filter, q, sort, showAll, median]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of data?.rows ?? []) if (r.reading !== "nothing") c[r.reading] = (c[r.reading] ?? 0) + 1;
    return c;
  }, [data]);

  const Th = ({ k, children, className = "" }:
    { k?: SortKey; children: React.ReactNode; className?: string }) => (
    <th className={`px-4 py-2.5 font-medium ${className}`}>
      {k ? (
        <button
          onClick={() => setSort(k)}
          className="inline-flex items-center gap-1 transition hover:opacity-80"
          style={{ color: sort === k ? "var(--ink)" : "inherit" }}
        >
          {children}
          {sort === k && <span className="text-[9px]">▼</span>}
        </button>
      ) : children}
    </th>
  );

  return (
    <div className="space-y-6">
      <SectionHead title="The board" right={
        data ? <span className="text-xs" style={{ color: "var(--ink-3)" }}>
          updated {ago(data.at)} · {data.universe} assets
        </span> : null
      }>
        <strong style={{ color: "var(--ink)" }}>Looked up</strong> is the asset&rsquo;s position
        on CoinMarketCap&rsquo;s most-visited list — what people are researching, not what
        they are posting about. Beneath it is the market-cap rank, and the gap between the
        two is the point. Price is judged on its excess over the universe median, so a coin
        up 3% on a day the median is up 4% counts as falling behind.
      </SectionHead>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => {
          const on = filter === f;
          const label = f === "all" ? "All" : READINGS[f].label;
          const n = f === "all"
            ? Object.values(counts).reduce((a, b) => a + b, 0)
            : counts[f] ?? 0;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="relative rounded-lg border px-3 py-1.5 text-sm transition hair"
              style={{
                background: on ? "var(--bg-2)" : "transparent",
                color: on ? "var(--ink)" : "var(--ink-2)",
                borderColor: on ? "var(--line-2)" : "var(--line)",
              }}
            >
              <span className="inline-flex items-center gap-1.5">
                {f !== "all" && (
                  <i className="size-2 rounded-full" style={{ background: READINGS[f].color }} />
                )}
                {label}
                <span className="num text-[11px]" style={{ color: "var(--ink-3)" }}>{n}</span>
              </span>
            </button>
          );
        })}
        <div className="flex-1" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search symbol…"
          className="rounded-lg border hair px-3 py-1.5 text-sm outline-none transition focus:border-[var(--line-2)]"
          style={{ background: "var(--bg-1)", color: "var(--ink)" }}
        />
        <button
          onClick={() => setShowAll((v) => !v)}
          className="rounded-lg border hair px-3 py-1.5 text-sm transition hover:bg-[var(--bg-2)]"
          style={{ color: "var(--ink-2)" }}
        >
          {showAll ? "Only flagged" : "Show all"}
        </button>
      </div>

      <Card className="overflow-x-auto">
        {loading ? (
          <div className="p-4"><Skeleton rows={10} /></div>
        ) : rows.length === 0 ? (
          <Empty>Nothing matches. That is a real answer, not a missing one.</Empty>
        ) : (
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="border-b hair text-xs" style={{ color: "var(--ink-2)" }}>
                <Th k="attention" className="text-left">Looked up</Th>
                <Th className="text-left">Asset</Th>
                <Th className="text-left">Reading</Th>
                <Th k="move" className="text-right">24h</Th>
                <Th k="excess" className="text-right">vs market</Th>
                <Th className="text-right">Price</Th>
                <Th k="wallets" className="text-right">Wallets</Th>
                <Th className="text-left">Why</Th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {rows.slice(0, 120).map((r, i) => (
                  <motion.tr
                    key={r.id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18, delay: Math.min(i, 12) * 0.012 }}
                    className="border-b hair last:border-0 transition hover:bg-[var(--bg-2)]"
                  >
                    <td className="px-4 py-2.5">
                      <AttentionCell rank={r.attention_rank} cap={r.rank} gap={r.attention_over_cap} />
                    </td>
                    <td className="px-4 py-2.5 font-medium"><AssetLink symbol={r.symbol} /></td>
                    <td className="px-4 py-2.5"><Pill reading={r.reading} /></td>
                    <td className="px-4 py-2.5 text-right num"><Signed v={r.pct_24h} dp={1} /></td>
                    <td className="px-4 py-2.5 text-right num">
                      <Signed v={r.pct_24h == null ? null : r.pct_24h - median} dp={1} />
                    </td>
                    <td className="px-4 py-2.5 text-right num" style={{ color: "var(--ink-2)" }}>
                      {price(r.price)}
                    </td>
                    <td className="px-4 py-2.5 text-right num" style={{ color: "var(--ink-2)" }}>
                      {r.wallet_count ? r.wallet_count.toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-[13px]" style={{ color: "var(--ink-2)" }}>
                      {r.why}
                      {!r.confident && (
                        <span className="ml-1 text-[11px]" style={{ color: "var(--ink-3)" }}>
                          · unconfirmed
                        </span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        )}
      </Card>

      {data && !data.attention_available && (
        <p className="text-sm" style={{ color: "var(--ink-3)" }}>
          CoinMarketCap&rsquo;s most-visited feed is not available on this API plan right
          now, so the crowd axis falls back to wallet growth where it exists and turnover
          where it does not. Readings resting on the proxy are marked unconfirmed and are
          not graded.
        </p>
      )}
    </div>
  );
}
