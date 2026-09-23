"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Latest, READINGS, useData, pct } from "@/lib/data";

type Item = { kind: "page" | "asset"; label: string; hint?: string; go: () => void; key: string };

/**
 * Cmd/Ctrl-K. A screener with three hundred assets and no keyboard route into them is a
 * screener people scroll rather than use.
 */
export default function Palette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const { data } = useData<Latest>("latest.json", 300_000);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
      // "/" is the search shortcut everywhere else, so honour it - but never while the
      // reader is typing into something.
      const el = document.activeElement?.tagName;
      if (e.key === "/" && el !== "INPUT" && el !== "TEXTAREA") {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) { setQ(""); setSel(0); setTimeout(() => inputRef.current?.focus(), 30); }
  }, [open]);

  const items = useMemo<Item[]>(() => {
    const go = (href: string) => () => { setOpen(false); router.push(href); };
    const pages: Item[] = [
      { kind: "page", key: "p-overview", label: "Overview", hint: "the claim, and today's widest gap", go: go("/") },
      { kind: "page", key: "p-board", label: "Board", hint: "everything carrying a reading", go: go("/board") },
      { kind: "page", key: "p-score", label: "Scorecard", hint: "does any of this work", go: go("/scorecard") },
      { kind: "page", key: "p-method", label: "Method", hint: "how it is measured", go: go("/method") },
    ];
    const needle = q.trim().toUpperCase().replace(/^\$/, "");
    const assets: Item[] = (data?.rows ?? [])
      .filter((r) => !needle || r.symbol.includes(needle))
      .sort((a, b) => (a.attention_rank ?? 1e9) - (b.attention_rank ?? 1e9))
      .slice(0, 40)
      .map((r) => ({
        kind: "asset" as const,
        key: `a-${r.id}`,
        label: r.symbol,
        hint: [
          r.attention_rank ? `looked up #${r.attention_rank}` : null,
          r.rank ? `cap #${r.rank}` : null,
          r.pct_24h != null ? pct(r.pct_24h, 1) : null,
          r.reading !== "nothing" ? READINGS[r.reading].label : null,
        ].filter(Boolean).join(" · "),
        go: go(`/asset/?s=${encodeURIComponent(r.symbol)}`),
      }));
    const pageHits = needle
      ? pages.filter((p) => p.label.toUpperCase().includes(needle))
      : pages;
    return [...pageHits, ...assets];
  }, [q, data, router]);

  useEffect(() => { setSel(0); }, [q]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, items.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    if (e.key === "Enter") { e.preventDefault(); items[sel]?.go(); }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.14 }}
          className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]"
          style={{ background: "rgba(0,0,0,.55)", backdropFilter: "blur(3px)" }}
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.99 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-xl overflow-hidden rounded-xl border shadow-2xl hair"
            style={{ background: "var(--bg-1)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search assets, or jump to a page…"
              className="w-full border-b bg-transparent px-4 py-3.5 text-[15px] outline-none hair"
              style={{ color: "var(--ink)" }}
            />
            <div className="max-h-[52vh] overflow-y-auto py-1">
              {items.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm" style={{ color: "var(--ink-3)" }}>
                  Nothing matching. The universe is the market-cap top 200 plus everything
                  on the most-visited list.
                </div>
              ) : items.map((it, i) => (
                <button
                  key={it.key}
                  onMouseEnter={() => setSel(i)}
                  onClick={it.go}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm"
                  style={{ background: i === sel ? "var(--bg-2)" : "transparent" }}
                >
                  <span
                    className="w-14 shrink-0 text-[10px] uppercase tracking-wider"
                    style={{ color: "var(--ink-3)" }}
                  >
                    {it.kind === "page" ? "Page" : "Asset"}
                  </span>
                  <span className="font-medium">{it.label}</span>
                  <span className="flex-1" />
                  <span className="truncate text-xs num" style={{ color: "var(--ink-3)" }}>
                    {it.hint}
                  </span>
                </button>
              ))}
            </div>
            <div
              className="flex items-center gap-4 border-t px-4 py-2 text-[11px] hair"
              style={{ color: "var(--ink-3)" }}
            >
              <span>↑↓ move</span><span>↵ open</span><span>esc close</span>
              <span className="flex-1" />
              <span>{items.length} results</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
