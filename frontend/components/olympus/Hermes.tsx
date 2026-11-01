"use client";
// Hermes, the task assistant: "Summarize" condenses a statement into four lines, "Hint"
// climbs a three-rung ladder (nudge → direction → approach). Hints are logged and lower the
// AI-efficiency score E, never correctness (BLUEPRINT §5). The text here is demo content;
// a live session gets it from the hint endpoint (P3.1).
import { useEffect, useState } from "react";
import Engraving from "./Engraving";
import { IconHermesWing, IconLock, IconSummarize, IconX } from "./Icons";

export function AiButton({
  kind,
  onClick,
  active,
  badge,
  disabled,
}: {
  kind: "summarize" | "hint";
  onClick: () => void;
  active?: boolean;
  badge?: string;
  disabled?: boolean;
}) {
  const Icon = kind === "summarize" ? IconSummarize : IconHermesWing;
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      title={kind === "summarize" ? "Hermes summarises this task" : "Ask Hermes for a hint"}
      className="group relative inline-flex h-9 items-center gap-2 overflow-hidden rounded-full pl-2.5 pr-3.5 text-[13px] font-medium transition-all duration-500 disabled:cursor-not-allowed disabled:opacity-40"
      style={{
        background: active ? "var(--ink)" : "rgba(35,55,165,0.06)",
        color: active ? "var(--parchment)" : "var(--ink)",
        boxShadow: active ? "none" : "inset 0 0 0 1px rgba(35,55,165,0.22)",
      }}
    >
      <span
        className="pointer-events-none absolute inset-0 -translate-x-full bg-[linear-gradient(100deg,transparent,rgba(226,194,134,0.45),transparent)] transition-transform duration-1000 group-hover:translate-x-full"
        aria-hidden="true"
      />
      <span className="grid h-6 w-6 place-items-center rounded-full transition-transform duration-500 group-hover:rotate-[-12deg]" style={{ background: active ? "rgba(255,255,255,0.14)" : "var(--parchment)" }}>
        <Icon size={14} />
      </span>
      {kind === "summarize" ? "AI Summarize" : "AI Hint"}
      {badge && <span className="mono ml-0.5 rounded-full bg-[rgba(184,147,90,0.18)] px-1.5 text-[10.5px] text-[#8a6a36]">{badge}</span>}
    </button>
  );
}

/** Lines appear one by one after a short "condensing" shimmer. */
export function HermesSummary({ lines, onClose }: { lines: string[]; onClose: () => void }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setShown((n) => (n > lines.length ? n : n + 1)), 420);
    return () => window.clearInterval(id);
  }, [lines.length]);
  return (
    <aside className="rise relative mb-6 overflow-hidden rounded-[18px] bg-[linear-gradient(135deg,rgba(35,55,165,0.07),rgba(226,194,134,0.12))] p-5 shadow-[inset_0_0_0_1px_rgba(184,147,90,0.4)]">
      <Engraving name="hermes-bust" className="pointer-events-none absolute -right-4 -top-3 w-28 opacity-[0.13]" />
      <div className="mb-3 flex items-center justify-between">
        <p className="eyebrow flex items-center gap-2 !text-[var(--ink)]">
          <IconSummarize size={14} /> Hermes · summary
        </p>
        <button className="icon-btn !h-7 !w-7" onClick={onClose} aria-label="Close summary">
          <IconX size={14} />
        </button>
      </div>
      {shown === 0 ? (
        <p className="shimmer text-[14px]">Hermes is condensing the scroll…</p>
      ) : (
        <ul className="space-y-2">
          {lines.slice(0, shown).map((l) => (
            <li key={l} className="rise flex gap-3 text-[14px] leading-relaxed">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rotate-45 bg-[var(--gold)]" />
              {l}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

const RUNGS = ["Nudge", "Direction", "Approach"];

export function HermesHints({
  hints,
  used,
  onReveal,
  onClose,
}: {
  hints: [string, string, string];
  used: number;
  onReveal: () => void;
  onClose: () => void;
}) {
  const [thinking, setThinking] = useState(false);
  const reveal = () => {
    setThinking(true);
    window.setTimeout(() => {
      setThinking(false);
      onReveal();
    }, 1100);
  };
  return (
    <aside className="rise relative mb-6 rounded-[18px] bg-[var(--parchment)] p-5 shadow-[inset_0_0_0_1px_var(--line-strong)]">
      <div className="mb-4 flex items-center justify-between">
        <p className="eyebrow flex items-center gap-2 !text-[var(--ink)]">
          <IconHermesWing size={14} /> Hermes · hint ladder
        </p>
        <button className="icon-btn !h-7 !w-7" onClick={onClose} aria-label="Close hints">
          <IconX size={14} />
        </button>
      </div>
      <ol className="relative space-y-3 pl-9">
        <span className="absolute bottom-3 left-[13px] top-3 w-px bg-[var(--line-strong)]" aria-hidden="true" />
        {hints.map((h, i) => {
          const open = i < used;
          const next = i === used;
          return (
            <li key={i} className="relative">
              <span
                className="numeral absolute -left-9 top-0.5 grid h-7 w-7 place-items-center rounded-full text-[13px]"
                style={{ background: open ? "var(--ink)" : "var(--parchment)", color: open ? "var(--parchment)" : "var(--text-3)", boxShadow: open ? "none" : "inset 0 0 0 1px var(--line-strong)" }}
              >
                {["i", "ii", "iii"][i]}
              </span>
              <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--text-3)]">
                {RUNGS[i]} · costs {i + 1} pt{i ? "s" : ""}
              </p>
              {open ? (
                <p className="rise mt-1 text-[14.5px] leading-relaxed">{h}</p>
              ) : next ? (
                thinking ? (
                  <p className="shimmer mt-1 text-[14px]">Hermes is choosing his words…</p>
                ) : (
                  <button onClick={reveal} className="mt-1.5 inline-flex items-center gap-2 text-[14px] font-medium text-[var(--ink)] underline decoration-[var(--line-strong)] underline-offset-4 hover:decoration-[var(--ink)]">
                    Reveal this hint
                  </button>
                )
              ) : (
                <p className="mt-1 flex items-center gap-2 text-[13.5px] text-[var(--text-3)]">
                  <IconLock size={13} /> Unlocks after the previous rung
                </p>
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-4 border-t border-[var(--line)] pt-3 text-[12.5px] leading-relaxed text-[var(--text-3)]">
        Hints lower your AI-efficiency score <span className="mono">E</span>, never correctness. Hermes never writes your fix.
      </p>
    </aside>
  );
}
