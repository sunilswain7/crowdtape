"use client";

import { useMemo, useRef, useState } from "react";
import { READINGS, Reading, SeriesPoint } from "@/lib/data";

type Pt = SeriesPoint;

/**
 * Two panels, one shared timeline.
 *
 * Above: the asset and the market median, both indexed to 100 at the start of the window,
 * so they sit on ONE axis and the gap between them IS the excess return the scorecard
 * grades. Below: position on the most-visited list, inverted so up means more looked-at.
 *
 * Separate panels rather than two scales on one plot. The alignment of two different
 * units is arbitrary, and a dual axis invents a correlation that is not in the data.
 */
export default function AssetChart({ pts, market, symbol, reading }:
  { pts: Pt[]; market: { t: string; i: number }[]; symbol: string; reading: Reading }) {
  const [hover, setHover] = useState<{ x: number; p: Pt; m?: { t: string; i: number } } | null>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const g = useMemo(() => {
    const valid = pts.filter((p) => p.i != null);
    if (valid.length < 2) return null;
    const W = 1000, PH = 230, AH = 118, P = { t: 16, r: 62, b: 22, l: 46 };
    const ts = valid.map((p) => Date.parse(p.t));
    const x0 = Math.min(...ts), x1 = Math.max(...ts);
    const mk = market.filter((m) => Date.parse(m.t) >= x0);
    const vals = [...valid.map((p) => p.i!), ...mk.map((m) => m.i)];
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.14 || 1;
    lo -= pad; hi += pad;
    // Snap to a clean step so ticks read 100 / 105 / 110, never 101.8.
    const raw = (hi - lo) / 4, mag = 10 ** Math.floor(Math.log10(raw));
    const step = ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;

    const X = (t: number) => P.l + (W - P.l - P.r) * (t - x0) / (x1 - x0 || 1);
    const Y = (v: number) => P.t + (PH - P.t - P.b) * (1 - (v - lo) / (hi - lo || 1));
    const path = (a: { t: string; i: number | null }[]) =>
      a.map((p, i) => `${i ? "L" : "M"}${X(Date.parse(p.t))} ${Y(p.i!)}`).join("");

    const ticks: number[] = [];
    for (let v = lo; v <= hi + 1e-9; v += step) ticks.push(v);

    // attention panel
    const apts = pts.filter((p) => p.a != null);
    let att = null;
    if (apts.length >= 2) {
      const ranks = apts.map((p) => p.a!);
      const worst = Math.min(200, Math.max(...ranks) + 8);
      const best = Math.max(1, Math.min(...ranks) - 4);
      const AY = (v: number) => 14 + (AH - 32) * (v - best) / ((worst - best) || 1);
      // Gaps are information: leaving the list entirely is not the same as staying still,
      // so segments are drawn separately rather than joined across the hole.
      const segs: Pt[][] = [];
      let cur: Pt[] = [];
      for (const p of pts) {
        if (p.a == null) { if (cur.length > 1) segs.push(cur); cur = []; }
        else cur.push(p);
      }
      if (cur.length > 1) segs.push(cur);
      const astep = Math.max(1, Math.round((worst - best) / 3));
      const aticks: number[] = [];
      for (let v = best; v <= worst; v += astep) aticks.push(v);
      att = { AY, segs, aticks, last: apts[apts.length - 1], AH };
    }
    return { W, PH, P, X, Y, path, ticks, valid, mk, att, x0, x1 };
  }, [pts, market]);

  if (!g) {
    return (
      <div className="px-4 py-12 text-center text-sm" style={{ color: "var(--ink-3)" }}>
        Not enough snapshots yet for {symbol}. The recorder takes one every ten minutes.
      </div>
    );
  }

  const colour = READINGS[reading].color;
  const last = g.valid[g.valid.length - 1];
  const lastM = g.mk[g.mk.length - 1];

  const onMove = (e: React.MouseEvent) => {
    const el = wrap.current?.querySelector("svg");
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * g.W;
    let best = g.valid[0], bd = Infinity;
    for (const p of g.valid) {
      const d = Math.abs(g.X(Date.parse(p.t)) - px);
      if (d < bd) { bd = d; best = p; }
    }
    const m = g.mk.reduce<{ t: string; i: number } | undefined>((a, b) =>
      !a || Math.abs(Date.parse(b.t) - Date.parse(best.t)) < Math.abs(Date.parse(a.t) - Date.parse(best.t))
        ? b : a, undefined);
    setHover({ x: g.X(Date.parse(best.t)), p: best, m });
  };

  return (
    <div ref={wrap} className="relative" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <div className="mb-3 flex flex-wrap gap-4 text-[13px]" style={{ color: "var(--ink-2)" }}>
        <span className="inline-flex items-center gap-2">
          <i className="size-2 rounded-full" style={{ background: colour }} />{symbol}
        </span>
        <span className="inline-flex items-center gap-2">
          <i className="size-2 rounded-full" style={{ background: "var(--ink-3)" }} />Market median
        </span>
        {g.att && (
          <span className="inline-flex items-center gap-2">
            <i className="size-2 rounded-full" style={{ background: "var(--color-quiet)" }} />
            Looked up (lower is more)
          </span>
        )}
      </div>

      <svg viewBox={`0 0 ${g.W} ${g.PH}`} className="w-full block overflow-visible"
           role="img" aria-label={`${symbol} indexed against the market median`}>
        {g.ticks.map((v) => (
          <g key={v}>
            <line x1={g.P.l} x2={g.W - g.P.r} y1={g.Y(v)} y2={g.Y(v)}
                  stroke="var(--line)" strokeWidth={1} />
            <text x={g.P.l - 8} y={g.Y(v) + 4} textAnchor="end"
                  className="num" fontSize={11} fill="var(--ink-3)">{v.toFixed(0)}</text>
          </g>
        ))}
        {g.mk.length > 1 && (
          <path d={g.path(g.mk)} fill="none" stroke="var(--ink-3)" strokeWidth={2}
                strokeLinejoin="round" strokeLinecap="round" />
        )}
        <path d={g.path(g.valid)} fill="none" stroke={colour} strokeWidth={2}
              strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={g.X(Date.parse(last.t))} cy={g.Y(last.i!)} r={4.5}
                fill={colour} stroke="var(--bg-1)" strokeWidth={2} />
        <text x={g.X(Date.parse(last.t)) + 9} y={g.Y(last.i!) + 4} fontSize={11}
              className="num" fill="var(--ink)">{last.i!.toFixed(1)}</text>
        {lastM && (
          <text x={g.X(Date.parse(lastM.t)) + 9} y={g.Y(lastM.i) + 4} fontSize={11}
                className="num" fill="var(--ink-3)">{lastM.i.toFixed(1)}</text>
        )}
        {hover && (
          <line x1={hover.x} x2={hover.x} y1={g.P.t} y2={g.PH - g.P.b}
                stroke="var(--line-2)" strokeWidth={1} />
        )}
      </svg>

      {g.att && (
        <svg viewBox={`0 0 ${g.W} ${g.att.AH}`} className="w-full block overflow-visible"
             role="img" aria-label={`${symbol} position on the most-visited list`}>
          {g.att.aticks.map((v) => (
            <g key={v}>
              <line x1={g.P.l} x2={g.W - g.P.r} y1={g.att!.AY(v)} y2={g.att!.AY(v)}
                    stroke="var(--line)" strokeWidth={1} />
              <text x={g.P.l - 8} y={g.att!.AY(v) + 4} textAnchor="end"
                    className="num" fontSize={11} fill="var(--ink-3)">#{Math.round(v)}</text>
            </g>
          ))}
          {g.att.segs.map((sg, i) => (
            <path key={i} fill="none" stroke="var(--color-quiet)" strokeWidth={2}
                  strokeLinejoin="round" strokeLinecap="round"
                  d={sg.map((p, j) => `${j ? "L" : "M"}${g.X(Date.parse(p.t))} ${g.att!.AY(p.a!)}`).join("")} />
          ))}
          <circle cx={g.X(Date.parse(g.att.last.t))} cy={g.att.AY(g.att.last.a!)} r={4.5}
                  fill="var(--color-quiet)" stroke="var(--bg-1)" strokeWidth={2} />
          <text x={g.X(Date.parse(g.att.last.t)) + 9} y={g.att.AY(g.att.last.a!) + 4}
                fontSize={11} className="num" fill="var(--ink)">#{g.att.last.a}</text>
          {hover && (
            <line x1={hover.x} x2={hover.x} y1={8} y2={g.att.AH - 14}
                  stroke="var(--line-2)" strokeWidth={1} />
          )}
        </svg>
      )}

      {/* reading strip, sharing the same timeline */}
      <svg viewBox={`0 0 ${g.W} 22`} className="w-full block mt-1" role="img"
           aria-label="Reading at each snapshot">
        {pts.map((p, i) => {
          const xa = g.X(Date.parse(p.t));
          const xb = i + 1 < pts.length ? g.X(Date.parse(pts[i + 1].t)) : xa + 5;
          return (
            <rect key={i} x={xa} y={5} width={Math.max(1.5, xb - xa - 1)} height={10} rx={3}
                  fill={READINGS[p.r].color} opacity={p.r === "nothing" ? 0.18 : 0.95}>
              <title>{new Date(p.t).toUTCString()} — {READINGS[p.r].label}</title>
            </rect>
          );
        })}
      </svg>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border hair px-3 py-2 text-xs num shadow-xl"
          style={{
            background: "var(--bg-1)", color: "var(--ink)",
            left: `calc(${(hover.x / g.W) * 100}% + 12px)`, top: 8,
            transform: hover.x / g.W > 0.75 ? "translateX(calc(-100% - 24px))" : undefined,
          }}
        >
          <div className="font-semibold">{new Date(hover.p.t).toUTCString().slice(5, 22)} UTC</div>
          <div className="mt-1">{symbol} {hover.p.i?.toFixed(2)} · market {hover.m?.i.toFixed(2) ?? "—"}</div>
          <div style={{ color: "var(--ink-2)" }}>
            excess {hover.m && hover.p.i != null
              ? `${hover.p.i - hover.m.i >= 0 ? "+" : ""}${(hover.p.i - hover.m.i).toFixed(2)} pts`
              : "—"}
            {hover.p.a != null && ` · looked up #${hover.p.a}`}
          </div>
          <div style={{ color: READINGS[hover.p.r].color }}>{READINGS[hover.p.r].label}</div>
        </div>
      )}
    </div>
  );
}
