"use client";

import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  EventRow, Latest, READINGS, Scorecard, Series, SeriesPoint,
  useData, ago, money, pct, price, LEVERAGE,
} from "@/lib/data";
import { Card, Empty, Pill, Signed, Skeleton } from "@/components/ui";
import AssetChart from "@/components/AssetChart";

function AssetView() {
  const params = useSearchParams();
  const symbol = (params.get("s") ?? "").toUpperCase();
  const { data: latest, loading } = useData<Latest>("latest.json");
  const { data: series } = useData<Series>("series.json");
  const { data: score } = useData<Scorecard>("scorecard.json");
  const { data: events } = useData<EventRow[]>("events.json");

  const row = latest?.rows.find((r) => r.symbol === symbol);
  const pts = useMemo(
    () => (row && series ? ((series[String(row.id)] as SeriesPoint[]) ?? []) : []),
    [row, series]);
  const market = (series?.["__market__"] as { t: string; i: number }[]) ?? [];
  const mine = (events ?? []).filter((e) => e.symbol === symbol).slice(0, 12);
  const median = latest?.median_move_24h ?? 0;

  if (loading) return <Skeleton rows={8} />;
  if (!symbol) return <Empty>Pick an asset from the <Link href="/board" className="underline">board</Link>.</Empty>;
  if (!row) {
    return (
      <Empty>
        <strong>{symbol}</strong> is not in the universe right now. That is the market-cap
        top 200 plus everything on CoinMarketCap&rsquo;s most-visited list.
        <div className="mt-3"><Link href="/board" className="underline">Back to the board</Link></div>
      </Empty>
    );
  }

  const excess = row.pct_24h == null ? null : row.pct_24h - median;
  const verdict = score?.verdicts?.[row.reading];
  const weak = verdict && (verdict.verdict === "rejected" || verdict.verdict === "no edge");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">{row.symbol}</h1>
        <span className="num text-sm" style={{ color: "var(--ink-3)" }}>
          market-cap rank #{row.rank ?? "—"}
        </span>
        <span className="flex-1" />
        <Link href="/board" className="text-sm hover:underline" style={{ color: "var(--accent)" }}>
          ← board
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { l: "Price", v: price(row.price) },
          { l: "24h", v: <Signed v={row.pct_24h} /> },
          { l: "vs market", v: <Signed v={excess} /> },
          { l: "Market cap", v: money(row.market_cap) },
        ].map((s, i) => (
          <Card key={s.l} delay={0.04 * i} className="p-4">
            <div className="text-xs" style={{ color: "var(--ink-2)" }}>{s.l}</div>
            <div className="mt-1 text-xl font-semibold num">{s.v}</div>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Pill reading={row.reading} />
          {!row.confident && (
            <span className="rounded-full border hair px-2 py-0.5 text-[10px] tracking-wider"
                  style={{ color: "var(--ink-3)" }}>UNCONFIRMED</span>
          )}
        </div>
        <p className="mt-2 text-[15px]" style={{ color: "var(--ink-2)" }}>{row.why}</p>
        {weak && (
          <div className="mt-4 rounded-lg border p-3 text-[13px]"
               style={{ borderColor: "var(--color-bad)", color: "var(--ink-2)" }}>
            <strong style={{ color: "var(--color-bad)" }}>
              This reading&rsquo;s own record is &ldquo;{verdict!.verdict}&rdquo;.
            </strong>{" "}
            {verdict!.why}{" "}
            <Link href="/scorecard" className="underline">See the scorecard</Link>.
          </div>
        )}
        {!row.confident && (
          <p className="mt-3 text-[13px]" style={{ color: "var(--ink-3)" }}>
            No wallet or attention measurement for this asset, so the crowd axis is
            turnover standing in for it. A proxy is not the same measurement, and readings
            resting on one are never graded.
          </p>
        )}
      </Card>

      <div className="grid gap-3 md:grid-cols-3">
        <Card className="p-4">
          <div className="text-xs" style={{ color: "var(--ink-2)" }}>Looked up</div>
          {row.attention_rank ? (
            <>
              <div className="mt-1 text-xl font-semibold num">#{row.attention_rank}</div>
              <div className="mt-0.5 text-xs" style={{ color: "var(--ink-3)" }}>
                on CoinMarketCap
                {row.attention_over_cap && row.attention_over_cap >= 2 &&
                  ` · ${Math.round(row.attention_over_cap)}× ahead of its size`}
              </div>
              {row.attention_rank_30d && (
                <div className="mt-1 text-xs" style={{ color: "var(--ink-3)" }}>
                  #{row.attention_rank_30d} over 30 days —{" "}
                  {row.attention_rank_30d > row.attention_rank + 40
                    ? "newer than it looks" : "a standing crowd"}
                </div>
              )}
            </>
          ) : (
            <div className="mt-1 text-sm" style={{ color: "var(--ink-3)" }}>
              {latest?.attention_available
                ? "Not in the most-visited 200 — measurably quiet"
                : "Attention feed unavailable on this plan"}
            </div>
          )}
        </Card>
        <Card className="p-4">
          <div className="text-xs" style={{ color: "var(--ink-2)" }}>Wallets holding</div>
          <div className="mt-1 text-xl font-semibold num">
            {row.wallet_count ? row.wallet_count.toLocaleString() : "—"}
          </div>
          <div className="mt-0.5 text-xs" style={{ color: "var(--ink-3)" }}>
            {row.wallet_growth != null
              ? `${(row.wallet_growth * 100).toFixed(3)}% since the last pass`
              : "no contract address CoinMarketCap's DEX index reaches"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs" style={{ color: "var(--ink-2)" }}>Leverage</div>
          <div className="mt-1 text-xl font-semibold">{LEVERAGE[row.leverage] ?? "—"}</div>
          <div className="mt-0.5 text-xs num" style={{ color: "var(--ink-3)" }}>
            {row.liq_long_24h != null
              ? `${money(row.liq_long_24h)} long · ${money(row.liq_short_24h)} short, 24h`
              : "no liquidation data"}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <h2 className="mb-1 text-base font-semibold">Against the market</h2>
        <p className="mb-4 max-w-3xl text-[13px] leading-relaxed" style={{ color: "var(--ink-2)" }}>
          Both lines indexed to 100 at the start of the window, so they share an axis and
          the gap between them <em>is</em> the excess return the scorecard grades. Below:
          where the asset sat on the most-visited list. Separate panels rather than two
          scales on one plot — the alignment of two different units is arbitrary and
          invents a correlation that is not in the data.
        </p>
        <AssetChart pts={pts} market={market} symbol={row.symbol} reading={row.reading} />
      </Card>

      {mine.length > 0 && (
        <Card className="overflow-hidden">
          <div className="border-b hair px-5 py-3">
            <h2 className="text-base font-semibold">Past calls on {row.symbol}</h2>
            <p className="mt-0.5 text-[13px]" style={{ color: "var(--ink-2)" }}>
              Graded on excess return over the market median. Misses included.
            </p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b hair text-xs" style={{ color: "var(--ink-2)" }}>
                <th className="px-5 py-2 text-left font-medium">Opened</th>
                <th className="px-5 py-2 text-left font-medium">Reading</th>
                <th className="px-5 py-2 text-right font-medium">+4h</th>
                <th className="px-5 py-2 text-right font-medium">+24h</th>
                <th className="px-5 py-2 text-right font-medium">+72h</th>
              </tr>
            </thead>
            <tbody>
              {mine.map((e, i) => (
                <tr key={i} className="border-b hair last:border-0">
                  <td className="px-5 py-2 num text-xs" style={{ color: "var(--ink-2)" }}>
                    {new Date(e.opened_at).toUTCString().slice(5, 17)}
                  </td>
                  <td className="px-5 py-2"><Pill reading={e.reading} /></td>
                  {["4", "24", "72"].map((h) => {
                    const s = e.scores?.[h];
                    if (!s) return <td key={h} className="px-5 py-2 text-right"
                                       style={{ color: "var(--ink-3)" }}>—</td>;
                    const ok = s.hit;
                    return (
                      <td key={h} className="px-5 py-2 text-right num"
                          style={{ color: ok == null ? "var(--ink-3)"
                                   : ok ? "var(--color-good)" : "var(--color-bad)" }}>
                        {(s.excess * 100 >= 0 ? "+" : "") + (s.excess * 100).toFixed(1)}%
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

export default function AssetPage() {
  return <Suspense fallback={<Skeleton rows={8} />}><AssetView /></Suspense>;
}
