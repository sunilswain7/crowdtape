"use client";

/** A sparkline. No axes, no labels - the number beside it carries the value. */
export default function Spark({ values, color, w = 120, h = 34 }:
  { values: (number | null | undefined)[]; color?: string; w?: number; h?: number }) {
  const v = values.filter((x): x is number => typeof x === "number");
  if (v.length < 2) return <div style={{ width: w, height: h }} />;
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const X = (i: number) => (w * i) / (v.length - 1);
  const Y = (n: number) => h - 3 - ((h - 6) * (n - lo)) / span;
  const line = v.map((n, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(n).toFixed(1)}`).join("");
  // Direction picks the colour when none is given: up is good, down is not.
  const c = color ?? (v[v.length - 1] >= v[0] ? "var(--color-good)" : "var(--color-bad)");
  const id = `sp${Math.abs(Math.round(v[0] * 1000 + v.length))}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={c} stopOpacity="0.22" />
          <stop offset="100%" stopColor={c} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line}L${w} ${h}L0 ${h}Z`} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={c} strokeWidth={1.6}
            strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
