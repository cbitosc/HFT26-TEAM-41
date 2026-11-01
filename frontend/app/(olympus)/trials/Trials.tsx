"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { JourneyBar, useCountdown } from "@/components/olympus/Chrome";
import CodePane from "@/components/olympus/CodePane";
import Engraving from "@/components/olympus/Engraving";
import { AiButton, HermesHints, HermesSummary } from "@/components/olympus/Hermes";
import { IconArrow, IconCheck, IconLock, IconPlay, IconX } from "@/components/olympus/Icons";
import { Btn } from "@/components/olympus/Kit";
import { useNav } from "@/components/olympus/Shell";
import { DEMO_PROFILE, firstName, forgedFrom, QUIZ, TRIAL_TASKS, type DemoTask } from "@/lib/olympus/demo";
import { updateJourney, useJourney, type TaskOutcome } from "@/lib/olympus/journey";
import { gsap, useGsap } from "@/lib/olympus/motion";

type RunState = { status: "idle" | "running" | "done"; results: boolean[] };
type Submitted = Record<string, TaskOutcome>;

export default function Trials() {
  const journey = useJourney();
  const { navigate } = useNav();
  const root = useRef<HTMLDivElement>(null);
  const seconds = useCountdown(60 * 60);
  const profile = journey.profile ?? DEMO_PROFILE;
  const [preview, setPreview] = useState(false); // demo only: show the Adept assistant on a Novice profile
  const assistant = profile.suggested_tier !== "novice" || preview;

  const [active, setActive] = useState<string>("domain");
  const [files, setFiles] = useState<Record<string, Record<string, string>>>(() =>
    Object.fromEntries(TRIAL_TASKS.map((t) => [t.id, Object.fromEntries(t.files.map((f) => [f.path, f.content]))])),
  );
  const [openFile, setOpenFile] = useState<Record<string, string>>({ domain: "app/utils.py", dsa: "solution.py" });
  const [runs, setRuns] = useState<Record<string, RunState>>({});
  const [runCount, setRunCount] = useState<Record<string, number>>({});
  const [panel, setPanel] = useState<Record<string, "summary" | "hints" | null>>({});
  const [hintsUsed, setHintsUsed] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState<Submitted>({});
  const [quiz, setQuiz] = useState<{ answers: (number | null)[]; sealed: boolean }>({ answers: QUIZ.map(() => null), sealed: false });
  const started = useRef(0);

  useGsap(root, (reduced) => {
    started.current = Date.now();
    if (reduced) return;
    gsap.from(".tr-in", { y: 30, opacity: 0, duration: 1.1, stagger: 0.08, ease: "expo.out", delay: 0.15 });
  });

  const task = TRIAL_TASKS.find((t) => t.id === active);
  const allDone = TRIAL_TASKS.every((t) => submitted[t.id]) && quiz.sealed;
  const hintLevels = TRIAL_TASKS.flatMap((t) => Array.from({ length: hintsUsed[t.id] ?? 0 }, (_, i) => i + 1));

  const run = (t: DemoTask) => {
    setRuns((r) => ({ ...r, [t.id]: { status: "running", results: [] } }));
    setRunCount((c) => ({ ...c, [t.id]: (c[t.id] ?? 0) + 1 }));
    window.setTimeout(() => setRuns((r) => ({ ...r, [t.id]: { status: "done", results: t.check(files[t.id]) } })), 1400);
  };

  const submit = (t: DemoTask) => {
    const results = t.check(files[t.id]);
    const passed = results.filter(Boolean).length;
    const allPass = passed === results.length;
    setSubmitted((s) => ({
      ...s,
      [t.id]: {
        id: t.id,
        title: t.title,
        kind: t.kind,
        visible: [passed, results.length],
        hidden: [allPass ? t.hiddenCount : Math.round((t.hiddenCount * passed) / results.length / 2), t.hiddenCount],
        runs: runCount[t.id] ?? 0,
        seconds: Math.round((Date.now() - started.current) / 1000),
      },
    }));
    const next = TRIAL_TASKS.find((x) => x.id !== t.id && !submitted[x.id]);
    setActive(next ? next.id : "quiz");
  };

  const complete = () => {
    updateJourney({
      trials: {
        tasks: TRIAL_TASKS.map((t) => submitted[t.id]),
        hintLevels,
        quiz: { correct: QUIZ.filter((q, i) => quiz.answers[i] === q.answer).length, total: QUIZ.length },
        completedAt: new Date().toISOString(),
      },
    });
    navigate("/labyrinth");
  };

  return (
    <div ref={root} className="shell">
      <JourneyBar seconds={seconds} />
      <div className="grid min-h-0 gap-4 overflow-y-auto p-4 lg:grid-cols-[290px_minmax(0,1fr)] xl:overflow-hidden">
        {/* ---------- Rail ---------- */}
        <aside className="scroll-y hidden min-h-0 flex-col gap-4 lg:flex">
          <div className="tr-in panel relative overflow-hidden p-5">
            <Engraving name="athena-helm-bust" className="pointer-events-none absolute -right-6 -top-2 w-28 opacity-[0.12]" />
            <p className="eyebrow">Forged for</p>
            <p className="display mt-1 text-[30px] leading-tight">{firstName(journey.candidate)}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="chip chip-ink !h-6 !text-[11.5px] capitalize">{profile.suggested_tier}</span>
              <span className="chip !h-6 !text-[11.5px]">{profile.domain}</span>
              <span className="chip !h-6 !text-[11.5px]">{profile.runtime}</span>
            </div>
            <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--text-2)]">{profile.tier_reason}</p>
            {journey.offline && <p className="mono mt-3 text-[11px] text-[#8a6a36]">Demo profile · API offline</p>}
          </div>

          <nav className="tr-in panel p-2" aria-label="Tasks">
            {[...TRIAL_TASKS.map((t) => ({ id: t.id, title: t.title, sub: t.subtitle })), { id: "quiz", title: "The Questioning", sub: `Technical round · ${QUIZ.length} questions` }].map(
              (t, i) => {
                const done = t.id === "quiz" ? quiz.sealed : !!submitted[t.id];
                const on = active === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => setActive(t.id)}
                    className="flex w-full items-start gap-3 rounded-[14px] p-3 text-left transition-colors duration-300"
                    style={{ background: on ? "rgba(35,55,165,0.08)" : "transparent" }}
                    aria-current={on ? "true" : undefined}
                  >
                    <span
                      className="numeral mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full text-[13px]"
                      style={{ background: done ? "var(--ink)" : "transparent", color: done ? "var(--parchment)" : "var(--ink)", boxShadow: done ? "none" : "inset 0 0 0 1px var(--line-strong)" }}
                    >
                      {done ? <IconCheck size={13} strokeWidth={2.2} /> : ["i", "ii", "iii"][i]}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[14.5px] font-medium">{t.title}</span>
                      <span className="block text-[12.5px] text-[var(--text-3)]">{t.sub}</span>
                    </span>
                  </button>
                );
              },
            )}
          </nav>

          <div className="tr-in panel p-5">
            <p className="eyebrow mb-3">Forged from</p>
            <div className="flex flex-wrap gap-1.5">
              {forgedFrom(journey).map((f) => (
                <span key={f} className="chip !h-6 !text-[11.5px]">
                  {f}
                </span>
              ))}
            </div>
          </div>

          <div className="tr-in mt-auto rounded-[18px] bg-[var(--ink)] p-5 text-[var(--parchment)]">
            <div className="flex items-center gap-3">
              <Engraving name="hermes-bust" className="w-12" style={{ color: "var(--parchment)" }} />
              <div>
                <p className="text-[14px] font-medium">Hermes {assistant ? "is with you" : "rests"}</p>
                <p className="text-[12px] opacity-70">{assistant ? `${hintLevels.length} hint${hintLevels.length === 1 ? "" : "s"} used · AI summarise free` : "Novice tier runs without an assistant"}</p>
              </div>
            </div>
            {profile.suggested_tier === "novice" && (
              <label className="mt-4 flex cursor-pointer items-center justify-between gap-3 border-t border-[rgba(7,11,38,0.18)] pt-3 text-[12.5px]">
                <span className="opacity-80">Preview the Adept assistant</span>
                <input type="checkbox" role="switch" checked={preview} onChange={(e) => setPreview(e.target.checked)} className="h-4 w-4 accent-[var(--gold-bright)]" />
              </label>
            )}
          </div>
        </aside>

        {/* ---------- Main ---------- */}
        {task ? (
          <TaskView
            key={task.id}
            task={task}
            files={files[task.id]}
            openFile={openFile[task.id]}
            setOpenFile={(p) => setOpenFile((o) => ({ ...o, [task.id]: p }))}
            setFile={(p, v) => setFiles((f) => ({ ...f, [task.id]: { ...f[task.id], [p]: v } }))}
            run={runs[task.id] ?? { status: "idle", results: [] }}
            runCount={runCount[task.id] ?? 0}
            onRun={() => run(task)}
            onSubmit={() => submit(task)}
            submitted={!!submitted[task.id]}
            panel={panel[task.id] ?? null}
            setPanel={(p) => setPanel((s) => ({ ...s, [task.id]: p }))}
            hintsUsed={hintsUsed[task.id] ?? 0}
            onHint={() => setHintsUsed((h) => ({ ...h, [task.id]: (h[task.id] ?? 0) + 1 }))}
            assistant={assistant}
          />
        ) : (
          <QuizView quiz={quiz} setQuiz={setQuiz} />
        )}
      </div>

      {allDone && (
        <div className="rise fixed bottom-6 left-1/2 z-40 flex w-[min(92vw,640px)] -translate-x-1/2 items-center justify-between gap-4 rounded-full bg-[var(--night-2)] py-2.5 pl-6 pr-2.5 text-[var(--moon)] shadow-[0_30px_60px_-20px_rgba(6,10,34,0.6)]">
          <span className="flex items-center gap-3 text-[14.5px]">
            <Engraving name="wreath" className="w-7" style={{ color: "var(--gold-bright)" }} />
            The Trials are complete.
          </span>
          <Btn variant="moon" size="sm" onClick={complete}>
            Enter the Labyrinth
          </Btn>
        </div>
      )}
    </div>
  );
}

function TaskView({
  task,
  files,
  openFile,
  setOpenFile,
  setFile,
  run,
  runCount,
  onRun,
  onSubmit,
  submitted,
  panel,
  setPanel,
  hintsUsed,
  onHint,
  assistant,
}: {
  task: DemoTask;
  files: Record<string, string>;
  openFile: string;
  setOpenFile: (p: string) => void;
  setFile: (p: string, v: string) => void;
  run: RunState;
  runCount: number;
  onRun: () => void;
  onSubmit: () => void;
  submitted: boolean;
  panel: "summary" | "hints" | null;
  setPanel: (p: "summary" | "hints" | null) => void;
  hintsUsed: number;
  onHint: () => void;
  assistant: boolean;
}) {
  const meta = task.files.find((f) => f.path === openFile);
  const passed = run.results.filter(Boolean).length;
  return (
    <div className="grid min-h-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)]">
      {/* Statement */}
      <section className="tr-in panel flex min-h-[420px] flex-col">
        <div className="panel-head flex-wrap">
          <div>
            <p className="eyebrow">{task.subtitle}</p>
          </div>
          <div className="flex items-center gap-2">
            <AiButton kind="summarize" active={panel === "summary"} onClick={() => setPanel(panel === "summary" ? null : "summary")} disabled={!assistant} />
            <AiButton kind="hint" active={panel === "hints"} badge={`${hintsUsed}/3`} onClick={() => setPanel(panel === "hints" ? null : "hints")} disabled={!assistant} />
          </div>
        </div>
        <div className="scroll-y min-h-0 flex-1 p-6">
          {panel === "summary" && <HermesSummary lines={task.summary} onClose={() => setPanel(null)} />}
          {panel === "hints" && <HermesHints hints={task.hints} used={hintsUsed} onReveal={onHint} onClose={() => setPanel(null)} />}
          <div className="prose-oly">
            <ReactMarkdown>{task.statement}</ReactMarkdown>
          </div>
        </div>
      </section>

      {/* Editor + console */}
      <section className="tr-in tablet flex min-h-[520px] flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-[rgba(233,228,212,0.08)] px-3">
          <div className="flex min-w-0 gap-1 overflow-x-auto" role="tablist">
            {task.files.map((f) => (
              <button
                key={f.path}
                role="tab"
                aria-selected={f.path === openFile}
                onClick={() => setOpenFile(f.path)}
                className="mono flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-[12.5px] transition-colors"
                style={{ borderColor: f.path === openFile ? "var(--gold-bright)" : "transparent", color: f.path === openFile ? "var(--moon)" : "rgba(233,228,212,0.5)" }}
              >
                {f.readOnly && <IconLock size={12} />}
                {f.path}
              </button>
            ))}
          </div>
          <span className="mono shrink-0 pr-2 text-[11px] text-[rgba(233,228,212,0.4)]">{meta?.readOnly ? "read-only" : "editable"}</span>
        </div>
        <div className="min-h-0 flex-1">
          <CodePane key={`${task.id}/${openFile}`} path={`${task.id}/${openFile}`} value={files[openFile]} readOnly={meta?.readOnly || submitted} onChange={(v) => setFile(openFile, v)} />
        </div>
        <div className="border-t border-[rgba(233,228,212,0.08)]">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <p className="eyebrow">
              Console {runCount > 0 && <span className="normal-case tracking-normal">· run {runCount}</span>}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={onRun}
                disabled={run.status === "running" || submitted}
                className="inline-flex h-9 items-center gap-2 rounded-full px-4 text-[13px] font-medium text-[var(--moon)] shadow-[inset_0_0_0_1px_rgba(233,228,212,0.25)] transition-colors hover:bg-[rgba(233,228,212,0.08)] disabled:opacity-40"
              >
                <IconPlay size={13} /> Run tests
              </button>
              <button
                onClick={onSubmit}
                disabled={submitted || run.status === "running"}
                className="inline-flex h-9 items-center gap-2 rounded-full bg-[var(--gold-bright)] px-4 text-[13px] font-semibold text-[var(--night)] transition-transform hover:-translate-y-0.5 disabled:opacity-40"
              >
                {submitted ? "Submitted" : "Submit"} <IconArrow size={13} />
              </button>
            </div>
          </div>
          <div className="scroll-y max-h-[190px] px-4 pb-4">
            {run.status === "idle" && <p className="mono text-[12.5px] text-[rgba(233,228,212,0.45)]">$ Run the visible tests whenever you like. Hidden tests run on submit.</p>}
            {run.status === "running" && <p className="shimmer mono text-[12.5px]">$ sealing a fresh sandbox · running {task.visibleTests.length} visible tests…</p>}
            {run.status === "done" && (
              <div className="rise">
                <p className="mono mb-2 text-[12.5px]" style={{ color: passed === run.results.length ? "#8fd6b0" : "#f2a990" }}>
                  {passed}/{run.results.length} visible tests passed
                </p>
                <ul className="grid gap-1 sm:grid-cols-2">
                  {task.visibleTests.map((name, i) => (
                    <li key={name} className="mono flex items-center gap-2 text-[12px] text-[rgba(233,228,212,0.8)]">
                      <span className="grid h-4 w-4 place-items-center rounded-full" style={{ background: run.results[i] ? "#2f7d5b" : "#b5473a" }}>
                        {run.results[i] ? <IconCheck size={10} strokeWidth={2.6} /> : <IconX size={10} strokeWidth={2.6} />}
                      </span>
                      <span className="truncate">{name}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mono mt-3 text-[10.5px] text-[rgba(233,228,212,0.3)]">Demo mode: runs are simulated in the browser. A live session runs them in a network-less sandbox.</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function QuizView({
  quiz,
  setQuiz,
}: {
  quiz: { answers: (number | null)[]; sealed: boolean };
  setQuiz: (q: { answers: (number | null)[]; sealed: boolean }) => void;
}) {
  const [i, setI] = useState(0);
  const q = QUIZ[i];
  const answered = quiz.answers.filter((a) => a !== null).length;
  const correct = QUIZ.filter((x, k) => quiz.answers[k] === x.answer).length;
  const choose = (opt: number) => {
    if (quiz.sealed) return;
    const answers = [...quiz.answers];
    answers[i] = opt;
    setQuiz({ ...quiz, answers });
  };
  return (
    <section className="tr-in panel relative flex min-h-0 flex-col overflow-hidden">
      <Engraving name="lyre" className="pointer-events-none absolute -bottom-6 right-6 w-44 opacity-[0.07]" />
      <div className="panel-head">
        <p className="eyebrow">The Questioning · personalised technical round</p>
        <div className="flex items-center gap-1.5" aria-label={`${answered} of ${QUIZ.length} answered`}>
          {QUIZ.map((_, k) => (
            <button
              key={k}
              onClick={() => setI(k)}
              aria-label={`Question ${k + 1}`}
              className="h-2 rounded-full transition-all duration-500"
              style={{ width: k === i ? 26 : 8, background: quiz.answers[k] !== null ? "var(--ink)" : "var(--line-strong)" }}
            />
          ))}
        </div>
      </div>
      <div className="scroll-y relative min-h-0 flex-1 p-6 md:p-10">
        <div key={q.id} className="rise mx-auto max-w-[760px]">
          <p className="chip chip-gold mb-5">Forged from · {q.basis}</p>
          <p className="numeral mb-2 text-[18px] text-[var(--ink)]">
            Question {["i", "ii", "iii", "iv", "v"][i]} of {QUIZ.length}
          </p>
          <h2 className="display text-[clamp(28px,3vw,42px)] leading-[1.1]">
            <ReactMarkdown components={{ p: ({ children }) => <>{children}</> }}>{q.prompt}</ReactMarkdown>
          </h2>
          {q.code && <pre className="mono mt-5 overflow-x-auto rounded-[14px] bg-[var(--night-2)] p-4 text-[13px] text-[var(--moon)]">{q.code}</pre>}
          <div className="mt-7 grid gap-3">
            {q.options.map((opt, k) => {
              const picked = quiz.answers[i] === k;
              const right = quiz.sealed && k === q.answer;
              const wrong = quiz.sealed && picked && k !== q.answer;
              return (
                <button
                  key={opt}
                  onClick={() => choose(k)}
                  className="group flex items-center gap-4 rounded-[16px] p-4 text-left transition-all duration-300 hover:-translate-y-0.5"
                  style={{
                    background: right ? "rgba(47,125,91,0.1)" : wrong ? "rgba(181,71,58,0.08)" : picked ? "rgba(35,55,165,0.08)" : "rgba(13,19,56,0.7)",
                    boxShadow: `inset 0 0 0 1px ${right ? "rgba(47,125,91,0.5)" : wrong ? "rgba(181,71,58,0.5)" : picked ? "var(--ink)" : "var(--line)"}`,
                  }}
                >
                  <span
                    className="numeral grid h-9 w-9 shrink-0 place-items-center rounded-full text-[16px] transition-colors"
                    style={{ background: picked ? "var(--ink)" : "transparent", color: picked ? "var(--parchment)" : "var(--ink)", boxShadow: picked ? "none" : "inset 0 0 0 1px var(--line-strong)" }}
                  >
                    {"ABCD"[k]}
                  </span>
                  <span className="text-[15.5px]">{opt}</span>
                  {right && <IconCheck className="ml-auto text-[var(--pass)]" />}
                </button>
              );
            })}
          </div>
          <div className="mt-8 flex items-center justify-between gap-4">
            <button onClick={() => setI(Math.max(0, i - 1))} disabled={i === 0} className="text-[14px] text-[var(--text-2)] disabled:opacity-30">
              ← Previous
            </button>
            {i < QUIZ.length - 1 ? (
              <Btn size="sm" onClick={() => setI(i + 1)} magnetic={false}>
                Next question
              </Btn>
            ) : quiz.sealed ? (
              <p className="display text-[24px]">
                {correct} of {QUIZ.length} correct
              </p>
            ) : (
              <Btn size="sm" onClick={() => setQuiz({ ...quiz, sealed: true })} disabled={answered < QUIZ.length} magnetic={false}>
                Seal your answers
              </Btn>
            )}
          </div>
          <p className="mt-6 text-[12.5px] text-[var(--text-3)]">Multiple choice is checked against a fixed key — no model grades your answers.</p>
        </div>
      </div>
    </section>
  );
}
