"use client";
// Navigation chrome: the wordmark, the landing-page nav and the journey bar that tops the
// assessment rounds (I Offering → V Verdict) with the countdown and the candidate seal.
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Engraving from "./Engraving";
import { IconCheck, IconClock } from "./Icons";
import { Btn } from "./Kit";
import { TLink } from "./Shell";
import { initials } from "@/lib/olympus/demo";
import { useJourney, type Journey } from "@/lib/olympus/journey";

export const BRAND = "Areté";

export function Logo({ night = false }: { night?: boolean }) {
  return (
    <TLink href="/" className="group flex items-center gap-2.5" aria-label={`${BRAND} home`}>
      <Engraving name="wreath" className={`w-7 transition-transform duration-700 group-hover:rotate-[20deg] ${night ? "text-[var(--moon)]" : ""}`} />
      <span className="display text-[26px] leading-none tracking-tight" style={{ fontWeight: 500 }}>
        {BRAND}
      </span>
    </TLink>
  );
}

export function SiteNav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 40);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header
      className="no-print fixed inset-x-0 top-0 z-50 transition-[padding,background,backdrop-filter] duration-500"
      style={{
        padding: scrolled ? "12px var(--gutter)" : "26px var(--gutter)",
        background: scrolled ? "rgba(7,11,38,0.78)" : "transparent",
        backdropFilter: scrolled ? "blur(14px) saturate(1.2)" : "none",
        borderBottom: scrolled ? "1px solid var(--line)" : "1px solid transparent",
      }}
    >
      <nav className="mx-auto flex max-w-[1600px] items-center justify-between gap-6">
        <Logo />
        <ul className="hidden items-center gap-9 text-[14px] text-[var(--text-2)] md:flex">
          {[
            ["#journey", "The journey"],
            ["#forge", "How it's forged"],
            ["#guides", "AI helpers"],
            ["#rules", "The laws"],
            ["/practice", "Practice"],
          ].map(([href, label]) => (
            <li key={href}>
              <a href={href} className="group relative py-1 transition-colors hover:text-[var(--text)]">
                {label}
                <span className="absolute inset-x-0 -bottom-0.5 h-px origin-right scale-x-0 bg-[var(--ink)] transition-transform duration-500 group-hover:origin-left group-hover:scale-x-100" />
              </a>
            </li>
          ))}
        </ul>
        <Btn href="/ascend" size="sm">
          Start with a portfolio
        </Btn>
      </nav>
    </header>
  );
}

const STAGES = [
  { href: "/ascend", numeral: "I", label: "Offering", done: (j: Journey) => !!j.candidate },
  { href: "/trials", numeral: "II", label: "Trials", done: (j: Journey) => !!j.trials },
  { href: "/labyrinth", numeral: "III", label: "Labyrinth", done: (j: Journey) => !!j.labyrinth },
  { href: "/oracle", numeral: "IV", label: "Oracle", done: (j: Journey) => !!j.oracle },
  { href: "/verdict", numeral: "V", label: "Verdict", done: (j: Journey) => !!j.reportAt },
];

/** Top bar of the assessment rounds. `seconds` shows a countdown chip when given. */
export function JourneyBar({ seconds, night = false }: { seconds?: number; night?: boolean }) {
  const pathname = usePathname();
  const journey = useJourney();
  const mm = seconds === undefined ? "" : `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const low = seconds !== undefined && seconds < 300;
  return (
    <header
      className="no-print relative z-20 flex items-center justify-between gap-4 px-[var(--gutter)] py-3"
      style={{ borderBottom: `1px solid ${night ? "rgba(233,228,212,0.1)" : "var(--line)"}` }}
    >
      <Logo night={night} />
      <ol className="hidden items-center gap-1 lg:flex" aria-label="Assessment rounds">
        {STAGES.map((s, i) => {
          const active = pathname === s.href;
          const done = s.done(journey);
          return (
            <li key={s.href} className="flex items-center gap-1">
              {i > 0 && <span className="h-px w-6" style={{ background: night ? "rgba(233,228,212,0.18)" : "var(--line-strong)" }} />}
              <TLink
                href={s.href}
                aria-current={active ? "step" : undefined}
                className="flex items-center gap-2 rounded-full px-3 py-1.5 text-[13px] transition-colors"
                style={{
                  background: active ? (night ? "var(--moon)" : "var(--ink)") : "transparent",
                  color: active ? (night ? "var(--night)" : "var(--parchment)") : night ? "rgba(233,228,212,0.6)" : "var(--text-2)",
                }}
              >
                <span
                  className="grid h-5 w-5 place-items-center rounded-full text-[10px]"
                  style={{
                    boxShadow: done || active ? "none" : `inset 0 0 0 1px ${night ? "rgba(233,228,212,0.3)" : "var(--line-strong)"}`,
                    background: done && !active ? (night ? "var(--gold-bright)" : "var(--ink)") : "transparent",
                    color: done && !active ? (night ? "var(--night)" : "var(--parchment)") : "inherit",
                  }}
                >
                  {done && !active ? <IconCheck size={11} strokeWidth={2.2} /> : <span className="numeral text-[11px]">{s.numeral}</span>}
                </span>
                {s.label}
              </TLink>
            </li>
          );
        })}
      </ol>
      <div className="flex items-center gap-3">
        {mm && (
          <span
            className="mono flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] tabular-nums"
            role="timer"
            aria-label={`Time left ${mm}`}
            style={{
              boxShadow: `inset 0 0 0 1px ${low ? "rgba(181,71,58,0.5)" : night ? "rgba(233,228,212,0.2)" : "var(--line-strong)"}`,
              color: low ? "var(--fail)" : undefined,
            }}
          >
            <IconClock size={14} />
            {mm}
          </span>
        )}
        <span
          className="grid h-9 w-9 place-items-center rounded-full text-[12px] font-semibold"
          style={{ background: night ? "var(--moon)" : "var(--ink)", color: night ? "var(--night)" : "var(--parchment)" }}
          title={journey.candidate?.name}
        >
          {initials(journey.candidate) || "—"}
        </span>
      </div>
    </header>
  );
}

/** Countdown in whole seconds; pauses while `running` is false and calls onExpire once at 0. */
export function useCountdown(totalSeconds: number, running = true, onExpire?: () => void): number {
  const [left, setLeft] = useState(totalSeconds);
  const expire = useRef(onExpire);
  useEffect(() => {
    expire.current = onExpire;
  });
  useEffect(() => {
    if (!running || left <= 0) return;
    const end = Date.now() + left * 1000;
    const id = window.setInterval(() => {
      const next = Math.max(0, Math.round((end - Date.now()) / 1000));
      setLeft(next);
      if (next === 0) {
        window.clearInterval(id);
        expire.current?.();
      }
    }, 1000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);
  return left;
}
