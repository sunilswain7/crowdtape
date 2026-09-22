"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { READINGS, Reading, pct } from "@/lib/data";

export const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
};

export function Card({ children, className = "", delay = 0 }:
  { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div
      {...fadeUp}
      transition={{ ...fadeUp.transition, delay }}
      className={`rounded-xl border hair ${className}`}
      style={{ background: "var(--bg-1)" }}
    >
      {children}
    </motion.div>
  );
}

export function Stat({ label, value, sub, accent = false, delay = 0 }:
  { label: string; value: React.ReactNode; sub?: React.ReactNode; accent?: boolean; delay?: number }) {
  return (
    <Card delay={delay} className="p-4">
      <div className="text-xs" style={{ color: "var(--ink-2)" }}>{label}</div>
      <div
        className="mt-1 text-2xl font-semibold tracking-tight num"
        style={{ color: accent ? "var(--accent)" : "var(--ink)" }}
      >
        {value}
      </div>
      {sub && <div className="mt-0.5 text-xs" style={{ color: "var(--ink-3)" }}>{sub}</div>}
    </Card>
  );
}

export function Pill({ reading }: { reading: Reading }) {
  const r = READINGS[reading];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px]">
      <i className="size-2 rounded-full shrink-0" style={{ background: r.color }} />
      {r.label}
    </span>
  );
}

/** The gap between how looked-at something is and how big it is. The point of all this. */
export function AttentionCell({ rank, cap, gap }:
  { rank: number | null; cap: number | null; gap: number | null }) {
  if (!rank) return <span style={{ color: "var(--ink-3)" }}>—</span>;
  return (
    <div className="leading-tight num">
      <div className="font-semibold">#{rank}</div>
      <div className="text-[11px]" style={{ color: "var(--ink-3)" }}>
        cap #{cap ?? "—"}
        {gap && gap >= 2 && (
          <span className="ml-1 font-semibold" style={{ color: gap >= 10 ? "var(--accent)" : "var(--ink-2)" }}>
            {Math.round(gap)}×
          </span>
        )}
      </div>
    </div>
  );
}

export function Signed({ v, dp = 2 }: { v: number | null; dp?: number }) {
  if (v == null) return <span style={{ color: "var(--ink-3)" }}>—</span>;
  return <span style={{ color: v >= 0 ? "var(--color-good)" : "var(--color-bad)" }}>{pct(v, dp)}</span>;
}

export function AssetLink({ symbol, children }: { symbol: string; children?: React.ReactNode }) {
  return (
    <Link href={`/asset/?s=${encodeURIComponent(symbol)}`} className="hover:underline">
      {children ?? symbol}
    </Link>
  );
}

export function Skeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-10 rounded-lg" />
      ))}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-4 py-10 text-center text-sm" style={{ color: "var(--ink-3)" }}>
      {children}
    </div>
  );
}

export function SectionHead({ title, children, right }:
  { title: string; children?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {children && (
          <p className="mt-1 max-w-3xl text-sm leading-relaxed" style={{ color: "var(--ink-2)" }}>
            {children}
          </p>
        )}
      </div>
      {right}
    </div>
  );
}
