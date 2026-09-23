"use client";

/**
 * The board holds no key and calls no API. It reads the JSON the recorder publishes
 * alongside it, so a new snapshot appears without rebuilding anything, and every number
 * on screen is reproducible from the repository with `python3 -m engine.report`.
 */
import { useEffect, useState } from "react";

export type Reading =
  | "loaded_spring" | "exit_liquidity" | "quiet_accumulation" | "capitulation" | "nothing";

export type Row = {
  id: number; symbol: string; rank: number | null;
  price: number | null; pct_24h: number | null;
  market_cap: number | null; volume_24h: number | null;
  reading: Reading; price_state: string; attention: string; leverage: string;
  why: string; confident: boolean;
  attention_rank: number | null; attention_rank_30d: number | null;
  attention_over_cap: number | null;
  wallet_count: number | null; wallet_growth: number | null;
  liq_long_24h: number | null; liq_short_24h: number | null;
};

export type Latest = {
  at: string; universe: number; snapshots_recorded: number; first_recorded: string;
  median_move_24h: number | null; attention_available: boolean;
  attention_covered?: number; wallets_covered?: number; holder_passes?: number;
  unavailable: Record<string, string>; rows: Row[];
};

export type Verdict = {
  verdict: "supported" | "rejected" | "no edge" | "not graded" | "too early";
  why: string; n: number; graded_confident: number; graded_proxied: number;
};

export type Scorecard = {
  generated_at: string; events_total: number; events_graded: number;
  verdicts: Record<string, Verdict>;
  cards: { reading: Reading; horizon_h: number; n: number; graded: number;
           hits: number; hit_rate: number | null; mean_excess: number;
           direction: number }[];
};

export type SeriesPoint = { t: string; p: number; i: number | null; a: number | null; r: Reading };
export type Series = Record<string, SeriesPoint[] | { t: string; i: number }[]>;

export type EventRow = {
  symbol: string; id: number; reading: Reading; opened_at: string;
  price_at_open: number; why: string; confident: boolean;
  scores: Record<string, { excess: number; coin: number; universe: number; hit: boolean | null }>;
};

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

async function grab<T>(file: string): Promise<T> {
  // Cache-bust: the recorder republishes these every few minutes and a stale board is
  // worse than a slow one.
  const res = await fetch(`${BASE}/data/${file}?t=${Math.floor(Date.now() / 60000)}`);
  if (!res.ok) throw new Error(`${file}: ${res.status}`);
  return res.json();
}

/**
 * Fetches a published file and keeps it fresh.
 *
 * The recorder takes a snapshot every ten minutes and redeploys, so an open tab polls
 * rather than going stale until someone reloads. Polling pauses while the tab is hidden -
 * a backgrounded tab refetching all night is rude and pointless - and refetches
 * immediately on return, so a tab left open overnight is current the moment it is looked
 * at rather than a minute later.
 */
export function useData<T>(file: string, everyMs = 60_000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<number>(0);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;

    const pull = () => {
      if (document.hidden) return schedule();
      grab<T>(file)
        .then((d) => { if (live) { setData(d); setError(null); setFetchedAt(Date.now()); } })
        .catch((e) => { if (live && !data) setError(String(e?.message ?? e)); })
        .finally(schedule);
    };
    const schedule = () => { if (live) timer = setTimeout(pull, everyMs); };
    const onVisible = () => { if (!document.hidden) { clearTimeout(timer); pull(); } };

    pull();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      live = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, everyMs]);

  return { data, error, loading: !data && !error, fetchedAt };
}

/** A clock that ticks, so "3 min ago" does not quietly become a lie. */
export function useNow(everyMs = 15_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}

// --- presentation ----------------------------------------------------------
export const READINGS: Record<Reading, { label: string; short: string; color: string; blurb: string }> = {
  loaded_spring: {
    label: "Loaded spring", short: "Spring", color: "var(--color-spring)",
    blurb: "Interest climbing while the price still tracks the market. Something building.",
  },
  exit_liquidity: {
    label: "Exit liquidity", short: "Exit", color: "var(--color-exit)",
    blurb: "Interest arriving after the move. You may be who they are selling to.",
  },
  quiet_accumulation: {
    label: "Quiet accumulation", short: "Quiet", color: "var(--color-quiet)",
    blurb: "Outperforming while interest sits below average. Moving without a crowd.",
  },
  capitulation: {
    label: "Capitulation", short: "Capit.", color: "var(--ink-3)",
    blurb: "Interest spiking while it falls behind. Claims no direction, so never graded.",
  },
  nothing: { label: "No reading", short: "—", color: "var(--ink-3)", blurb: "" },
};

export const LEVERAGE: Record<string, string> = {
  longs_flushing: "Longs flushing", shorts_squeezed: "Shorts squeezed",
  quiet: "Quiet", unknown: "—",
};

export const money = (v: number | null | undefined) => {
  // Zero means CoinMarketCap could not verify circulating supply, not that the asset is
  // worthless. Printing "$0" would state something false.
  if (!v) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
};

export const price = (v: number | null | undefined) =>
  v == null ? "—" : v >= 1 ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                           : `$${v.toPrecision(3)}`;

export const pct = (v: number | null | undefined, dp = 2) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(dp)}%`;

export const ago = (iso: string, now = Date.now()) => {
  const m = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
};
