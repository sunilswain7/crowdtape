"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import Palette from "@/components/Palette";
import Live from "@/components/Live";
import { Latest, useData } from "@/lib/data";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/board", label: "Board" },
  { href: "/scorecard", label: "Scorecard" },
  { href: "/method", label: "Method" },
];

const ACCENTS = [
  { key: "blue", hex: "#3987e5" },
  { key: "aqua", hex: "#199e70" },
  { key: "amber", hex: "#eda100" },
  { key: "violet", hex: "#9085e9" },
];

function Settings() {
  const [theme, setTheme] = useState("dark");
  const [accent, setAccent] = useState("blue");

  useEffect(() => {
    try {
      const t = localStorage.getItem("ct-theme") ?? "dark";
      const a = localStorage.getItem("ct-accent") ?? "blue";
      setTheme(t); setAccent(a);
    } catch { /* private mode: defaults are fine */ }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.accent = accent;
    try {
      localStorage.setItem("ct-theme", theme);
      localStorage.setItem("ct-accent", accent);
    } catch { /* nothing to do */ }
  }, [theme, accent]);

  return (
    <div className="flex items-center gap-3">
      <div className="hidden sm:flex items-center gap-1.5">
        {ACCENTS.map((a) => (
          <button
            key={a.key}
            onClick={() => setAccent(a.key)}
            aria-label={`Accent ${a.key}`}
            aria-pressed={accent === a.key}
            className="size-3.5 rounded-full transition-transform hover:scale-125"
            style={{
              background: a.hex,
              outline: accent === a.key ? "2px solid var(--ink-2)" : "none",
              outlineOffset: 2,
            }}
          />
        ))}
      </div>
      <button
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        className="rounded-lg border px-2.5 py-1.5 text-xs hair hover:bg-[var(--bg-2)] transition"
        style={{ color: "var(--ink-2)" }}
        aria-label="Switch theme"
      >
        {theme === "dark" ? "Dark" : "Light"}
      </button>
    </div>
  );
}

function SearchHint() {
  const [mac, setMac] = useState(false);
  useEffect(() => { setMac(/Mac|iPhone|iPad/.test(navigator.platform)); }, []);
  return (
    <button
      onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
      className="hidden lg:inline-flex items-center gap-2 rounded-lg border hair px-2.5 py-1.5 text-xs transition hover:bg-[var(--bg-2)]"
      style={{ color: "var(--ink-3)" }}
      aria-label="Search"
    >
      Search
      <kbd className="rounded border hair px-1 py-0.5 text-[10px]">{mac ? "⌘" : "Ctrl"} K</kbd>
    </button>
  );
}

export default function Chrome({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { data: latest } = useData<Latest>("latest.json", 60_000);
  const active = (href: string) =>
    href === "/" ? path === "/" || path === "" : path.startsWith(href);

  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="sticky top-0 z-40 border-b hair backdrop-blur-xl"
        style={{ background: "color-mix(in oklab, var(--bg) 82%, transparent)" }}
      >
        <div className="mx-auto max-w-[1400px] px-4 sm:px-6">
          <div className="flex h-14 items-center gap-2">
            <Link href="/" className="flex items-center gap-2.5 shrink-0">
              <span
                className="grid size-7 place-items-center rounded-md text-[13px] font-bold"
                style={{ background: "var(--accent)", color: "#fff" }}
              >
                C
              </span>
              <span className="font-semibold tracking-tight">Crowdtape</span>
            </Link>

            <nav className="ml-4 hidden md:flex items-center gap-1">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="relative px-3 py-1.5 text-sm rounded-lg transition"
                  style={{ color: active(n.href) ? "var(--ink)" : "var(--ink-2)" }}
                >
                  {active(n.href) && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-lg -z-10"
                      style={{ background: "var(--bg-2)" }}
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                  {n.label}
                </Link>
              ))}
            </nav>

            <div className="flex-1" />
            <div className="hidden md:block"><Live latest={latest} /></div>
            <SearchHint />
            <a
              href="https://t.me/crowdtape_bot"
              target="_blank"
              rel="noopener"
              className="hidden sm:inline-flex rounded-lg px-3 py-1.5 text-sm font-medium transition hover:opacity-90"
              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
            >
              Telegram
            </a>
            <Settings />
          </div>

          <div className="flex md:hidden items-center gap-2 pb-1">
            <Live latest={latest} />
          </div>
          <nav className="flex md:hidden gap-1 pb-2 -mx-1 overflow-x-auto">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="whitespace-nowrap rounded-lg px-3 py-1.5 text-sm"
                style={{
                  color: active(n.href) ? "var(--ink)" : "var(--ink-2)",
                  background: active(n.href) ? "var(--bg-2)" : "transparent",
                }}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <Palette />
      <main className="flex-1 mx-auto w-full max-w-[1400px] px-4 sm:px-6 py-8">{children}</main>

      <footer className="border-t hair mt-12">
        <div className="mx-auto max-w-[1400px] px-4 sm:px-6 py-8 text-sm" style={{ color: "var(--ink-3)" }}>
          <p className="max-w-3xl">
            Built on the CoinMarketCap API for the Build with CMC hackathon. The board is
            static and holds no key: every number regenerates from the recorded snapshots
            in the repository with one command.
          </p>
          <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1">
            <a className="hover:underline" href="https://github.com/sunilswain7/crowdtape">Source and data</a>
            <a className="hover:underline" href="https://t.me/crowdtape_bot">@crowdtape_bot</a>
            <Link className="hover:underline" href="/method">How it works</Link>
            <span>Not investment advice.</span>
          </p>
        </div>
      </footer>
    </div>
  );
}
