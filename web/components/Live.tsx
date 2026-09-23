"use client";

import { Latest, ago, useNow } from "@/lib/data";

/**
 * Says how fresh the board is, and keeps saying it.
 *
 * The snapshot timestamp is not the same as "when this page last checked", and conflating
 * them hides a stale deploy - which is exactly how the published board sat twenty-one
 * hours behind the repository without anything on screen admitting it. Green means the
 * data really is recent; amber says plainly that it is not.
 */
export default function Live({ latest }: { latest: Latest | null }) {
  const now = useNow(15_000);
  if (!latest) return <span className="text-xs" style={{ color: "var(--ink-3)" }}>connecting…</span>;

  const mins = (now - Date.parse(latest.at)) / 60000;
  const fresh = mins < 25;

  return (
    <span className="inline-flex items-center gap-2 text-xs num" title={new Date(latest.at).toUTCString()}>
      <span className="relative flex size-2">
        {fresh && (
          <span
            className="absolute inline-flex size-full animate-ping rounded-full opacity-60"
            style={{ background: "var(--color-good)" }}
          />
        )}
        <span
          className="relative inline-flex size-2 rounded-full"
          style={{ background: fresh ? "var(--color-good)" : "#eda100" }}
        />
      </span>
      <span style={{ color: fresh ? "var(--ink-2)" : "#eda100" }}>
        {fresh ? `updated ${ago(latest.at, now)}` : `last snapshot ${ago(latest.at, now)}`}
      </span>
    </span>
  );
}
