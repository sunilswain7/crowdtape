"use client";

import { motion } from "framer-motion";

/**
 * Fear and greed, as an arc.
 *
 * The scale is semantic rather than categorical - fear at one end, greed at the other -
 * so it gets a warm/cool ramp with the needle riding it, not one of the reading hues.
 * Those are reserved for identity and must never be borrowed for a value scale.
 */
export default function Gauge({ value, label }: { value: number | null; label?: string }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const R = 52, C = Math.PI * R;           // semicircle length
  const stops = ["#ea3943", "#f59e0b", "#eab308", "#84cc16", "#16c784"];
  const colour = stops[Math.min(4, Math.floor(v / 20))];

  return (
    <div className="flex items-center gap-4">
      <svg width={128} height={76} viewBox="0 0 128 76" className="shrink-0" aria-hidden>
        <defs>
          <linearGradient id="fg" x1="0" y1="0" x2="1" y2="0">
            {stops.map((s, i) => (
              <stop key={s} offset={`${(i / (stops.length - 1)) * 100}%`} stopColor={s} />
            ))}
          </linearGradient>
        </defs>
        <path d={`M12 66 A ${R} ${R} 0 0 1 116 66`} fill="none"
              stroke="var(--bg-3)" strokeWidth={11} strokeLinecap="round" />
        <motion.path
          d={`M12 66 A ${R} ${R} 0 0 1 116 66`} fill="none"
          stroke="url(#fg)" strokeWidth={11} strokeLinecap="round"
          strokeDasharray={C}
          initial={{ strokeDashoffset: C }}
          animate={{ strokeDashoffset: C - (C * v) / 100 }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
        <motion.circle
          r={5} fill={colour} stroke="var(--bg-1)" strokeWidth={2.5}
          initial={{ cx: 12, cy: 66 }}
          animate={{
            cx: 64 - R * Math.cos((v / 100) * Math.PI),
            cy: 66 - R * Math.sin((v / 100) * Math.PI),
          }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div>
        <div className="text-3xl font-semibold num" style={{ color: colour }}>
          {value ?? "—"}
        </div>
        <div className="text-xs" style={{ color: "var(--ink-2)" }}>{label ?? "Fear & Greed"}</div>
      </div>
    </div>
  );
}
