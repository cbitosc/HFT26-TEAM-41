"use client";

import { useMemo, useRef, useState, type ReactNode } from "react";
import Ariadne from "@/components/olympus/Ariadne";
import { JourneyBar, useCountdown } from "@/components/olympus/Chrome";
import CodePane from "@/components/olympus/CodePane";
import Engraving from "@/components/olympus/Engraving";
import { IconBranch, IconBug, IconCheck, IconEye, IconFile, IconFolder, IconGauge, IconStar, IconX } from "@/components/olympus/Icons";
import { Btn } from "@/components/olympus/Kit";
import { useNav } from "@/components/olympus/Shell";
import { LABYRINTH_FILES, LABYRINTH_ISSUES, LABYRINTH_REPO } from "@/lib/olympus/demo";
import { updateJourney } from "@/lib/olympus/journey";
import { gsap, useGsap } from "@/lib/olympus/motion";

type Tab = "issues" | "analysis" | "debug" | "optimise";
type Finding = { file: string; line: string; note: string };
type PerfIdea = { where: string; now: string; proposal: string };

export default function Labyrinth() {
  const { navigate } = useNav();
  const root = useRef<HTMLDivElement>(null);
  const seconds = useCountdown(30 * 60);
  const [open, setOpen] = useState("app/dispatch.py");
  const [code, setCode] = useState<Record<string, string>>(() => Object.fromEntries(LABYRINTH_FILES.map((f) => [f.path, f.content])));
  const [tab, setTab] = useState<Tab>("issues");
  const [issueNotes, setIssueNotes] = useState<Record<number, string>>({});
  const [resolved, setResolved] = useState<Record<number, boolean>>({});
  const [expanded, setExpanded] = useState<number | null>(12);
  const [analysis, setAnalysis] = useState("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [ideas, setIdeas] = useState<PerfIdea[]>([]);
  const [asked, setAsked] = useState(0);

  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.from(".lb-in", { y: 30, opacity: 0, duration: 1.1, stagger: 0.08, ease: "expo.out", delay: 0.15 });
  });

  const touched = LABYRINTH_FILES.filter((f) => code[f.path] !== f.content).map((f) => f.path);
  const resolvedCount = Object.values(resolved).filter(Boolean).length;
  const words = analysis.trim() ? analysis.trim().split(/\s+/).length : 0;
  const progress = Math.min(1, (resolvedCount / 3) * 0.5 + (Math.min(findings.length, 3) / 3) * 0.2 + (Math.min(ideas.length, 2) / 2) * 0.15 + Math.min(words / 60, 1) * 0.15);

  const tree = useMemo(() => {
    const dirs: Record<string, string[]> = {};
    for (const f of LABYRINTH_FILES) {
      const parts = f.path.split("/");
      const dir = parts.length > 1 ? parts[0] : "";
      (dirs[dir] ??= []).push(f.path);
    }
    return Object.entries(dirs).sort(([a], [b]) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b)));
  }, []);

  const finish = () => {
    updateJourney({
      labyrinth: {
        issuesResolved: resolvedCount,
        issuesTotal: LABYRINTH_ISSUES.length,
        findings: findings.length,
        perfIdeas: ideas.length,
        filesTouched: touched.length,
        questionsAsked: asked,
        completedAt: new Date().toISOString(),
      },
    });
    navigate("/oracle");
  };

  return (
    <div ref={root} className="shell">
      <JourneyBar seconds={seconds} />
      <div className="grid min-h-0 gap-4 overflow-y-auto p-4 xl:grid-cols-[230px_minmax(0,1fr)_400px] xl:overflow-hidden">
        {/* ---------- Repo + tree ---------- */}
        <aside className="lb-in panel scroll-y flex min-h-0 flex-col">
          <div className="relative overflow-hidden border-b border-[var(--line)] p-4">
            <Engraving name="minotaur" className="pointer-events-none absolute -right-6 bottom-1 w-32 opacity-[0.12]" />
            <p className="mono text-[11.5px] text-[var(--text-3)]">{LABYRINTH_REPO.owner} /</p>
            <p className="text-[17px] font-semibold">{LABYRINTH_REPO.name}</p>
            <p className="mt-2 text-[12.5px] leading-relaxed text-[var(--text-2)]">{LABYRINTH_REPO.description}</p>
            <div className="mono mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-[var(--text-2)]">
              <span className="flex items-center gap-1">
                <IconStar size={12} /> {LABYRINTH_REPO.stars}
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-[#3572A5]" /> {LABYRINTH_REPO.language}
              </span>
              <span className="flex items-center gap-1">
                <IconBranch size={12} /> {LABYRINTH_REPO.branch}
              </span>
            </div>
          </div>
          <nav className="p-2 text-[13px]" aria-label="Files">
            {tree.map(([dir, paths]) => (
              <div key={dir || "root"} className="mb-1">
                {dir && (
                  <p className="flex items-center gap-2 px-2 py-1.5 text-[var(--text-2)]">
                    <IconFolder size={14} /> {dir}
                  </p>
                )}
                {paths.map((p) => (
                  <button
                    key={p}
                    onClick={() => setOpen(p)}
                    aria-current={open === p ? "true" : undefined}
                    className="mono flex w-full items-center gap-2 rounded-[10px] py-1.5 pr-2 text-left text-[12.5px] transition-colors"
                    style={{ paddingLeft: dir ? 26 : 8, background: open === p ? "rgba(35,55,165,0.09)" : "transparent", color: open === p ? "var(--ink)" : "var(--text)" }}
                  >
                    <IconFile size={13} />
                    <span className="truncate">{p.split("/").pop()}</span>
                    {touched.includes(p) && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--gold)]" title="Modified" />}
                  </button>
                ))}
              </div>
            ))}
          </nav>
          <div className="mt-auto border-t border-[var(--line)] p-4">
            <ThreadMeter progress={progress} />
          </div>
        </aside>

        {/* ---------- Code ---------- */}
        <section className="lb-in tablet flex min-h-[520px] flex-col">
          <div className="flex items-center justify-between border-b border-[rgba(233,228,212,0.08)] px-4 py-3">
            <p className="mono flex items-center gap-2 text-[12.5px] text-[var(--moon)]">
              <IconFile size={13} /> {open}
            </p>
            <p className="mono text-[11px] text-[rgba(233,228,212,0.45)]">{touched.includes(open) ? "modified · edits are part of your findings" : "editable · try a fix"}</p>
          </div>
          <div className="min-h-0 flex-1">
            <CodePane key={open} path={`labyrinth/${open}`} value={code[open]} onChange={(v) => setCode((c) => ({ ...c, [open]: v }))} />
          </div>
        </section>

        {/* ---------- Findings ---------- */}
        <section className="lb-in panel flex min-h-[520px] flex-col">
          <div className="flex gap-5 border-b border-[var(--line)] px-5 pt-3" role="tablist">
            {(
              [
                ["issues", `Issues ${resolvedCount}/${LABYRINTH_ISSUES.length}`],
                ["analysis", "Analyse"],
                ["debug", `Debug ${findings.length || ""}`],
                ["optimise", `Optimise ${ideas.length || ""}`],
              ] as [Tab, string][]
            ).map(([id, label]) => (
              <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)} className="tab">
                {label}
              </button>
            ))}
          </div>

          <div className="scroll-y min-h-0 flex-1 p-5">
            {tab === "issues" && (
              <div className="space-y-3">
                <p className="text-[13.5px] text-[var(--text-2)]">Three reported issues. Find each cause, describe the fix, and mark it resolved.</p>
                {LABYRINTH_ISSUES.map((iss) => {
                  const isOpen = expanded === iss.id;
                  return (
                    <article key={iss.id} className="overflow-hidden rounded-[16px] bg-[rgba(13,19,56,0.8)] shadow-[inset_0_0_0_1px_var(--line)]">
                      <button className="flex w-full items-start gap-3 p-4 text-left" onClick={() => setExpanded(isOpen ? null : iss.id)} aria-expanded={isOpen}>
                        <span
                          className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full"
                          style={{ background: resolved[iss.id] ? "var(--pass)" : iss.label === "bug" ? "rgba(181,71,58,0.12)" : "rgba(184,147,90,0.2)", color: resolved[iss.id] ? "#fff" : iss.label === "bug" ? "var(--fail)" : "#8a6a36" }}
                        >
                          {resolved[iss.id] ? <IconCheck size={12} strokeWidth={2.4} /> : iss.label === "bug" ? <IconBug size={13} /> : <IconGauge size={13} />}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="mono text-[11.5px] text-[var(--text-3)]">#{iss.id} · {iss.label}</span>
                          <span className="block text-[14.5px] font-medium leading-snug">{iss.title}</span>
                        </span>
                      </button>
                      {isOpen && (
                        <div className="rise border-t border-[var(--line)] p-4">
                          <p className="text-[13.5px] leading-relaxed text-[var(--text-2)]">{iss.body}</p>
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {iss.files.map((f) => (
                              <button key={f} onClick={() => setOpen(f)} className="chip mono !h-6 !text-[11px] hover:bg-[rgba(35,55,165,0.06)]">
                                <IconEye size={12} /> {f}
                              </button>
                            ))}
                          </div>
                          <TextArea
                            label="Root cause and fix"
                            value={issueNotes[iss.id] ?? ""}
                            onChange={(v) => setIssueNotes((n) => ({ ...n, [iss.id]: v }))}
                            rows={4}
                          />
                          <div className="mt-3 flex justify-end">
                            <button
                              onClick={() => setResolved((r) => ({ ...r, [iss.id]: !r[iss.id] }))}
                              disabled={!resolved[iss.id] && (issueNotes[iss.id] ?? "").trim().length < 12}
                              className="inline-flex h-9 items-center gap-2 rounded-full px-4 text-[13px] font-medium transition-colors disabled:opacity-40"
                              style={resolved[iss.id] ? { background: "var(--pass)", color: "#fff" } : { background: "var(--ink)", color: "var(--parchment)" }}
                            >
                              <IconCheck size={13} /> {resolved[iss.id] ? "Resolved" : "Mark resolved"}
                            </button>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}

            {tab === "analysis" && (
              <div>
                <p className="display text-[26px] leading-tight">Map the labyrinth</p>
                <p className="mt-2 text-[13.5px] leading-relaxed text-[var(--text-2)]">In your own words: how does a request flow through this service, and where would you look first when it misbehaves?</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {["Entry points", "Data flow", "State & caching", "Risky assumptions"].map((p) => (
                    <span key={p} className="chip !h-6 !text-[11.5px]">
                      {p}
                    </span>
                  ))}
                </div>
                <TextArea label="Your analysis" value={analysis} onChange={setAnalysis} rows={12} />
                <p className="mono mt-2 text-right text-[11.5px] text-[var(--text-3)]">{words} words</p>
              </div>
            )}

            {tab === "debug" && (
              <EntryList
                intro="Log each defect you find — even ones no issue mentions."
                empty="No defects logged yet."
                fields={[
                  { key: "file", label: "File", options: LABYRINTH_FILES.filter((f) => f.path.endsWith(".py")).map((f) => f.path) },
                  { key: "line", label: "Line", short: true },
                  { key: "note", label: "What's wrong, and why it matters", long: true },
                ]}
                items={findings}
                onAdd={(e) => setFindings((f) => [...f, e as Finding])}
                onRemove={(i) => setFindings((f) => f.filter((_, k) => k !== i))}
                render={(f: Finding) => (
                  <>
                    <p className="mono text-[11.5px] text-[var(--ink)]">
                      {f.file}
                      {f.line && `:${f.line}`}
                    </p>
                    <p className="mt-1 text-[13.5px]">{f.note}</p>
                  </>
                )}
                icon={<IconBug size={14} />}
              />
            )}

            {tab === "optimise" && (
              <EntryList
                intro="How would you make hermes-courier faster and leaner? Name the cost today and what you'd change."
                empty="No proposals yet."
                fields={[
                  { key: "where", label: "Where (file · function)" },
                  { key: "now", label: "Cost today (e.g. O(n²), N+1 queries)" },
                  { key: "proposal", label: "Your improvement and expected gain", long: true },
                ]}
                items={ideas}
                onAdd={(e) => setIdeas((f) => [...f, e as PerfIdea])}
                onRemove={(i) => setIdeas((f) => f.filter((_, k) => k !== i))}
                render={(p: PerfIdea) => (
                  <>
                    <p className="mono text-[11.5px] text-[var(--ink)]">{p.where}</p>
                    <p className="mt-1 text-[13px] text-[var(--fail)]">{p.now}</p>
                    <p className="mt-1 text-[13.5px]">→ {p.proposal}</p>
                  </>
                )}
                icon={<IconGauge size={14} />}
              />
            )}
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-[var(--line)] p-4">
            <p className="text-[12.5px] text-[var(--text-2)]">
              {resolvedCount} resolved · {findings.length} defects · {ideas.length} proposals
            </p>
            <Btn size="sm" magnetic={false} onClick={finish} disabled={progress < 0.15}>
              Leave the Labyrinth
            </Btn>
          </div>
        </section>
      </div>
      <Ariadne onAsk={() => setAsked((n) => n + 1)} />
    </div>
  );
}

/** Ariadne's thread: a gold line winding through a small maze as findings accumulate. */
function ThreadMeter({ progress }: { progress: number }) {
  const d = "M6 54 H34 V34 H14 V14 H54 V44 H74 V6 H94 V54 H114";
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <p className="eyebrow">Ariadne&apos;s thread</p>
        <p className="mono text-[11.5px] text-[var(--ink)]">{Math.round(progress * 100)}%</p>
      </div>
      <svg viewBox="0 0 120 60" className="w-full" aria-hidden="true">
        <path d={d} fill="none" stroke="var(--line-strong)" strokeWidth="5" strokeLinejoin="round" />
        <path d={d} fill="none" stroke="var(--gold)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={1 - progress} style={{ transition: "stroke-dashoffset 1s var(--ease-out)" }} />
      </svg>
    </div>
  );
}

function TextArea({ label, value, onChange, rows }: { label: string; value: string; onChange: (v: string) => void; rows: number }) {
  return (
    <label className="mt-3 block">
      <span className="sr-only">{label}</span>
      <textarea
        value={value}
        rows={rows}
        placeholder={`${label}…`}
        onChange={(e) => onChange(e.target.value)}
        className="w-full resize-y rounded-[14px] bg-[rgba(13,19,56,0.95)] p-3 text-[14px] leading-relaxed shadow-[inset_0_0_0_1px_var(--line-strong)] outline-none transition-shadow placeholder:text-[var(--text-3)] focus:shadow-[inset_0_0_0_1.5px_var(--ink)]"
      />
    </label>
  );
}

type FieldDef = { key: string; label: string; options?: string[]; short?: boolean; long?: boolean };

function EntryList<T extends Record<string, string>>({
  intro,
  empty,
  fields,
  items,
  onAdd,
  onRemove,
  render,
  icon,
}: {
  intro: string;
  empty: string;
  fields: FieldDef[];
  items: T[];
  onAdd: (entry: Record<string, string>) => void;
  onRemove: (i: number) => void;
  render: (item: T) => ReactNode;
  icon: ReactNode;
}) {
  const blank = Object.fromEntries(fields.map((f) => [f.key, f.options?.[0] ?? ""]));
  const [entry, setEntry] = useState<Record<string, string>>(blank);
  const last = fields[fields.length - 1].key;
  const input = "w-full rounded-[12px] bg-[rgba(13,19,56,0.95)] px-3 py-2 text-[13.5px] shadow-[inset_0_0_0_1px_var(--line-strong)] outline-none focus:shadow-[inset_0_0_0_1.5px_var(--ink)]";
  return (
    <div>
      <p className="text-[13.5px] leading-relaxed text-[var(--text-2)]">{intro}</p>
      <form
        className="mt-4 space-y-2 rounded-[16px] bg-[rgba(35,55,165,0.04)] p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!entry[last]?.trim()) return;
          onAdd(entry);
          setEntry(blank);
        }}
      >
        <div className="flex gap-2">
          {fields
            .filter((f) => !f.long)
            .map((f) =>
              f.options ? (
                <select key={f.key} aria-label={f.label} value={entry[f.key]} onChange={(e) => setEntry({ ...entry, [f.key]: e.target.value })} className={`${input} mono !text-[12px]`}>
                  {f.options.map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </select>
              ) : (
                <input
                  key={f.key}
                  aria-label={f.label}
                  placeholder={f.label}
                  value={entry[f.key]}
                  onChange={(e) => setEntry({ ...entry, [f.key]: e.target.value })}
                  className={`${input} ${f.short ? "!w-20 shrink-0" : ""}`}
                />
              ),
            )}
        </div>
        {fields
          .filter((f) => f.long)
          .map((f) => (
            <textarea key={f.key} aria-label={f.label} placeholder={f.label} rows={3} value={entry[f.key]} onChange={(e) => setEntry({ ...entry, [f.key]: e.target.value })} className={`${input} resize-y`} />
          ))}
        <div className="flex justify-end">
          <button type="submit" disabled={!entry[last]?.trim()} className="inline-flex h-8 items-center gap-2 rounded-full bg-[var(--ink)] px-3.5 text-[12.5px] font-medium text-[var(--parchment)] disabled:opacity-40">
            {icon} Add to the scroll
          </button>
        </div>
      </form>
      <ul className="mt-4 space-y-2">
        {items.length === 0 && <li className="py-6 text-center text-[13px] text-[var(--text-3)]">{empty}</li>}
        {items.map((it, i) => (
          <li key={i} className="rise group relative rounded-[14px] bg-[rgba(13,19,56,0.85)] p-3 pr-10 shadow-[inset_0_0_0_1px_var(--line)]">
            {render(it)}
            <button onClick={() => onRemove(i)} className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-full text-[var(--text-3)] opacity-0 transition-opacity hover:bg-[rgba(181,71,58,0.1)] hover:text-[var(--fail)] group-hover:opacity-100 focus:opacity-100" aria-label="Remove">
              <IconX size={13} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
