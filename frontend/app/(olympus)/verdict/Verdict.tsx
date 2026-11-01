"use client";

import { useRef, useState, type ReactNode } from "react";
import { JourneyBar } from "@/components/olympus/Chrome";
import Engraving from "@/components/olympus/Engraving";
import { IconCheck, IconDownload, IconLink } from "@/components/olympus/Icons";
import { Btn, SmoothScroll } from "@/components/olympus/Kit";
import Meander from "@/components/olympus/Meander";
import { TLink, useNav } from "@/components/olympus/Shell";
import type { EngravingName } from "@/lib/olympus/engravings";
import { BAND_LABEL, correctnessOf, demoResults, displayName, verdictOf } from "@/lib/olympus/demo";
import { resetJourney, updateJourney, useHydrated, useJourney, type Journey } from "@/lib/olympus/journey";
import { gsap, useGsap } from "@/lib/olympus/motion";

export default function Verdict() {
  const journey = useJourney();
  const hydrated = useHydrated();
  const [forging, setForging] = useState(false);

  const generate = () => {
    setForging(true);
    window.setTimeout(() => {
      updateJourney({ reportAt: new Date().toISOString() });
      setForging(false);
    }, 3200);
  };

  return (
    <div className="min-h-screen">
      <SmoothScroll />
      <div className="sticky top-0 z-40 bg-[rgba(7,11,38,0.8)] backdrop-blur-md">
        <JourneyBar />
      </div>
      {!hydrated ? null : journey.reportAt && journey.trials && journey.labyrinth && journey.oracle ? (
        <Report journey={journey} />
      ) : (
        <Tribunal journey={journey} onGenerate={generate} />
      )}
      {forging && <Forging />}
    </div>
  );
}

function Tribunal({ journey, onGenerate }: { journey: Journey; onGenerate: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.from(".tb-in", { y: 50, opacity: 0, duration: 1.3, stagger: 0.09, ease: "expo.out", delay: 0.15 });
  });
  const rounds: { key: "trials" | "labyrinth" | "oracle"; title: string; href: string; art: EngravingName; note: string }[] = [
    { key: "trials", title: "Trials of Athena", href: "/trials", art: "athena", note: "Coding tasks & technical round" },
    { key: "labyrinth", title: "The Labyrinth", href: "/labyrinth", art: "minotaur", note: "Code comprehension" },
    { key: "oracle", title: "The Oracle", href: "/oracle", art: "sun", note: "Voice interview" },
  ];
  const done = rounds.filter((r) => journey[r.key]).length;
  return (
    <main ref={root} className="mx-auto max-w-[1300px] px-[var(--gutter)] py-16 text-center">
      <p className="eyebrow tb-in">Round Ⅴ · The Verdict</p>
      <h1 className="display tb-in mx-auto mt-5 max-w-[900px] text-[clamp(52px,7vw,120px)]">
        The tribunal <em className="text-[var(--ink)]">assembles.</em>
      </h1>
      <p className="tb-in mx-auto mt-6 max-w-[540px] text-[17px] leading-relaxed text-[var(--text-2)]">
        When all three rounds are sealed, generate your report. It is computed from test results and fixed formulas — the same deeds
        always earn the same verdict.
      </p>
      <div className="mt-14 grid gap-5 md:grid-cols-3">
        {rounds.map((r, i) => {
          const sealed = !!journey[r.key];
          return (
            <TLink
              key={r.key}
              href={r.href}
              className="tb-in engr-host group relative flex flex-col items-center overflow-hidden rounded-[26px] bg-[var(--parchment-2)] px-6 pb-8 pt-10 shadow-[inset_0_0_0_1px_var(--line)] transition-transform duration-700 hover:-translate-y-1.5"
            >
              <span className="numeral absolute left-6 top-5 text-[22px] text-[var(--ink)]">{["Ⅱ", "Ⅲ", "Ⅳ"][i]}</span>
              <span
                className="absolute right-5 top-5 flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium"
                style={sealed ? { background: "var(--ink)", color: "var(--parchment)" } : { boxShadow: "inset 0 0 0 1px var(--line-strong)", color: "var(--text-2)" }}
              >
                {sealed ? (
                  <>
                    <IconCheck size={12} strokeWidth={2.4} /> Sealed
                  </>
                ) : (
                  "Pending"
                )}
              </span>
              <div className="flex h-[220px] items-end">
                <Engraving name={r.art} sheen className="h-[200px] w-auto" style={{ opacity: sealed ? 1 : 0.35 }} />
              </div>
              <p className="display mt-6 text-[32px]">{r.title}</p>
              <p className="mt-1 text-[14px] text-[var(--text-2)]">{r.note}</p>
            </TLink>
          );
        })}
      </div>
      <div className="tb-in mt-14 flex flex-col items-center gap-4">
        <Btn onClick={onGenerate} disabled={done < 3}>
          Generate report
        </Btn>
        <p className="text-[14px] text-[var(--text-3)]">
          {done < 3 ? `${3 - done} round${3 - done === 1 ? "" : "s"} still open. ` : "All rounds sealed. "}
          {done < 3 && (
            <button className="text-[var(--ink)] underline underline-offset-4" onClick={() => updateJourney((j) => demoResults(j))}>
              Fill the open rounds with sample results
            </button>
          )}
        </p>
      </div>
    </main>
  );
}

function Forging() {
  const root = useRef<HTMLDivElement>(null);
  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.fromTo(root.current, { clipPath: "inset(100% 0 0 0)" }, { clipPath: "inset(0% 0 0 0)", duration: 1, ease: "expo.inOut" });
    gsap.from(".fg-wreath", { rotate: -180, scale: 0.3, opacity: 0, duration: 2.2, ease: "expo.out", delay: 0.4 });
    gsap.from(".fg-line", { y: 20, opacity: 0, stagger: 0.45, duration: 0.8, ease: "expo.out", delay: 0.7 });
  });
  return (
    <div ref={root} className="fixed inset-0 z-[120] grid place-items-center bg-[var(--ink)] text-[var(--parchment)]" role="status" aria-live="polite">
      <Meander className="absolute inset-x-0 top-8 text-[var(--parchment)] opacity-30" height={14} />
      <div className="text-center">
        <Engraving name="wreath" className="fg-wreath mx-auto w-40" style={{ color: "var(--gold-bright)" }} />
        <p className="display mt-8 text-[clamp(40px,5vw,72px)] italic">Weighing your deeds…</p>
        <div className="mono mt-6 space-y-2 text-[13px] opacity-80">
          <p className="fg-line">correctness = 100 × (0.3 × visible + 0.7 × hidden)</p>
          <p className="fg-line">final = 0.8 × mean(correctness) + 20 × E</p>
          <p className="fg-line">interview and comprehension · reported alongside</p>
        </div>
      </div>
      <Meander className="absolute inset-x-0 bottom-8 text-[var(--parchment)] opacity-30" height={14} />
    </div>
  );
}

function Report({ journey }: { journey: Journey }) {
  const { navigate } = useNav();
  const root = useRef<HTMLDivElement>(null);
  const v = verdictOf(journey);
  const trials = journey.trials!;
  const lab = journey.labyrinth!;
  const oracle = journey.oracle!;
  const [copied, setCopied] = useState(false);

  const quizRate = trials.quiz.total ? trials.quiz.correct / trials.quiz.total : 0;
  const labIndex = (lab.issuesResolved / Math.max(1, lab.issuesTotal)) * 0.6 + Math.min(lab.findings, 4) / 4 * 0.25 + Math.min(lab.perfIdeas, 2) / 2 * 0.15;
  const axes = [
    { label: "Debugging", value: v.correctness[0] / 100 },
    { label: "Algorithms", value: (v.correctness[1] ?? 0) / 100 },
    { label: "Fundamentals", value: quizRate },
    { label: "Comprehension", value: labIndex },
    { label: "Communication", value: oracle.total ? oracle.answered / oracle.total : 0 },
    { label: "Independence", value: 1 - Math.min(1, trials.hintLevels.reduce((a, b) => a + b, 0) / 12) },
  ];

  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.from(".rp-in", { y: 50, opacity: 0, duration: 1.3, stagger: 0.07, ease: "expo.out", delay: 0.1 });
    const o = { n: 0 };
    gsap.to(o, {
      n: v.final,
      duration: 2.6,
      ease: "expo.out",
      delay: 0.4,
      onUpdate: () => {
        const el = document.querySelector(".rp-score");
        if (el) el.textContent = o.n.toFixed(1);
      },
    });
    gsap.from(".rp-wreath", { rotate: -120, scale: 0.6, opacity: 0, duration: 2.2, ease: "expo.out" });
    gsap.from(".rp-poly", { scale: 0, transformOrigin: "50% 50%", duration: 1.8, ease: "expo.out", scrollTrigger: { trigger: ".rp-radar", start: "top 80%" } });
    gsap.utils.toArray<HTMLElement>(".rp-bar").forEach((el) => gsap.from(el, { scaleX: 0, duration: 1.6, ease: "expo.out", scrollTrigger: { trigger: el, start: "top 92%" } }));
  });

  const copy = async () => {
    const text = `${displayName(journey.candidate)} — ${v.final} (${BAND_LABEL[v.band]}), tier ${v.tier}. Trials: ${trials.tasks
      .map((t) => `${t.title} ${correctnessOf(t).toFixed(0)}`)
      .join(", ")}. Labyrinth: ${lab.issuesResolved}/${lab.issuesTotal} issues. Oracle: ${oracle.answered}/${oracle.total} answered (not scored).`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <main ref={root} className="mx-auto max-w-[1400px] px-[var(--gutter)] pb-24 pt-12">
      {/* Hero */}
      <section className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="eyebrow rp-in">The Verdict · {new Date(journey.reportAt!).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}</p>
          <h1 className="display rp-in mt-5 text-[clamp(52px,7vw,124px)]">{displayName(journey.candidate)}</h1>
          <div className="rp-in mt-6 flex flex-wrap gap-2">
            <span className="chip chip-ink capitalize">{v.tier} tier</span>
            <span className="chip">{BAND_LABEL[v.band]}</span>
            <span className="chip">{journey.offline ? "Demo grading" : "Graded from tests"}</span>
          </div>
          <p className="rp-in mt-7 max-w-[560px] text-[16px] leading-relaxed text-[var(--text-2)]">
            Final = 0.8 × mean correctness ({v.mean.toFixed(1)}) + 20 × AI efficiency ({v.efficiency.toFixed(2)}). The Labyrinth and the Oracle are reported
            beside the score and never change it.
          </p>
          <div className="no-print rp-in mt-8 flex flex-wrap gap-3">
            <Btn onClick={() => window.print()} icon={<IconDownload size={14} />}>
              Download PDF
            </Btn>
            <Btn variant="ghost" onClick={copy} icon={<IconLink size={14} />}>
              {copied ? "Copied" : "Copy summary"}
            </Btn>
          </div>
        </div>
        <div className="relative mx-auto grid aspect-square w-full max-w-[460px] place-items-center">
          <Engraving name="wreath-2" className="rp-wreath absolute inset-0 m-auto w-[82%] text-[var(--ink)] opacity-90" />
          <div className="relative -mt-[12%] rounded-full bg-[var(--parchment)] px-6 py-4 text-center">
            <p className="rp-score display text-[clamp(60px,7vw,108px)] tabular-nums leading-none text-[var(--ink)]">{v.final.toFixed(1)}</p>
            <p className="eyebrow mt-2">out of 100 · {BAND_LABEL[v.band]}</p>
          </div>
          <Engraving name="nike" className="pointer-events-none absolute -right-10 -top-8 w-36 opacity-25 md:-right-16" />
        </div>
      </section>

      <Meander className="rp-in my-16 opacity-40" height={14} />

      {/* Trials */}
      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card eyebrow="Ⅱ · Trials of Athena" title="Correctness" art="athena-helm-bust">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[14px]">
              <thead className="eyebrow !text-[10px]">
                <tr className="border-b border-[var(--line)]">
                  <th className="py-3 font-normal">Task</th>
                  <th className="py-3 font-normal">Visible</th>
                  <th className="py-3 font-normal">Hidden</th>
                  <th className="py-3 font-normal">Runs</th>
                  <th className="py-3 text-right font-normal">Score</th>
                </tr>
              </thead>
              <tbody>
                {trials.tasks.map((t, i) => (
                  <tr key={t.id} className="border-b border-[var(--line)]">
                    <td className="py-4">
                      <p className="font-medium">{t.title}</p>
                      <p className="text-[12.5px] text-[var(--text-3)]">{t.kind === "dsa" ? "Algorithm" : "Domain bug fix"} · {Math.round(t.seconds / 60)} min</p>
                    </td>
                    <td className="mono py-4">
                      {t.visible[0]}/{t.visible[1]}
                    </td>
                    <td className="mono py-4">
                      {t.hidden[0]}/{t.hidden[1]}
                    </td>
                    <td className="mono py-4">{t.runs}</td>
                    <td className="py-4 text-right">
                      <span className="display text-[30px] text-[var(--ink)]">{v.correctness[i].toFixed(0)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-[14px]">
            <span className="text-[var(--text-2)]">Technical round · fixed answer key</span>
            <span className="mono">
              {trials.quiz.correct}/{trials.quiz.total} correct
            </span>
          </div>
        </Card>

        <Card eyebrow="Hermes" title="AI efficiency" art="hermes-bust">
          <p className="display text-[64px] leading-none text-[var(--ink)]">{v.efficiency.toFixed(2)}</p>
          <Bar value={v.efficiency} />
          <p className="mt-4 text-[14px] leading-relaxed text-[var(--text-2)]">
            {trials.hintLevels.length === 0
              ? "No hints taken: E equals mean correctness ÷ 100."
              : `${trials.hintLevels.length} hint${trials.hintLevels.length === 1 ? "" : "s"} taken (levels ${trials.hintLevels.join(", ")}). Hints lower independence, never correctness.`}
          </p>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {["Nudge", "Direction", "Approach"].map((l, i) => (
              <span key={l} className="chip !h-6 !text-[11.5px]" style={trials.hintLevels.includes(i + 1) ? { background: "var(--ink)", color: "var(--parchment)", boxShadow: "none" } : undefined}>
                {l}
              </span>
            ))}
          </div>
        </Card>
      </section>

      {/* Labyrinth + constellation + Oracle */}
      <section className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card eyebrow="Ⅲ · The Labyrinth · reported" title="Comprehension" art="minotaur">
          <div className="grid grid-cols-2 gap-4">
            <Stat n={`${lab.issuesResolved}/${lab.issuesTotal}`} label="issues resolved" />
            <Stat n={lab.findings} label="defects logged" />
            <Stat n={lab.perfIdeas} label="performance proposals" />
            <Stat n={lab.questionsAsked} label="questions to Ariadne" />
          </div>
          <p className="mt-4 text-[13px] text-[var(--text-3)]">Comprehension index {(labIndex * 100).toFixed(0)} · not part of the final score.</p>
        </Card>

        <Card eyebrow="Constellation" title="Your profile" art="starchart">
          <Radar axes={axes} />
          <p className="mt-2 text-center text-[12px] text-[var(--text-3)]">Comprehension and communication are reported, not scored.</p>
        </Card>

        <Card eyebrow="Ⅳ · The Oracle · never scored" title="Interview" art="pythia-bust">
          <div className="grid grid-cols-2 gap-4">
            <Stat n={`${oracle.answered}/${oracle.total}`} label="questions answered" />
            <Stat n={`${Math.floor(oracle.seconds / 60)}:${String(oracle.seconds % 60).padStart(2, "0")}`} label="minutes spoken" />
          </div>
          <div className="mt-5 space-y-2">
            {oracle.transcript.slice(0, 3).map((x, i) => (
              <details key={i} className="group rounded-[14px] bg-[rgba(13,19,56,0.8)] p-3 shadow-[inset_0_0_0_1px_var(--line)]">
                <summary className="cursor-pointer list-none text-[13.5px] font-medium marker:hidden">
                  <span className="numeral mr-2 text-[var(--ink)]">{["i", "ii", "iii"][i]}.</span>
                  {x.q}
                </summary>
                <p className="mt-2 text-[13.5px] leading-relaxed text-[var(--text-2)]">{x.a}</p>
              </details>
            ))}
          </div>
        </Card>
      </section>

      {/* Integrity */}
      <section className="rp-in mt-6 flex flex-wrap items-center gap-6 rounded-[26px] bg-[var(--ink-deep)] p-8 text-[var(--moon)] md:p-10">
        <Engraving name="medusa" className="w-20" style={{ color: "var(--gold-bright)" }} />
        <div className="flex-1">
          <p className="eyebrow">Integrity · Medusa&apos;s gaze</p>
          <p className="display mt-2 text-[32px]">No flags raised.</p>
          <p className="mt-1 text-[14px] text-[rgba(233,228,212,0.7)]">Paste bursts, test-set tampering and suspicious code are checked on every run. Flags are shown here and never change the score.</p>
        </div>
        <div className="no-print flex gap-3">
          <Btn
            variant="moon"
            size="sm"
            onClick={() => {
              resetJourney();
              navigate("/ascend");
            }}
          >
            Begin again
          </Btn>
        </div>
      </section>
    </main>
  );
}

function Card({ eyebrow, title, art, children }: { eyebrow: string; title: string; art: EngravingName; children: ReactNode }) {
  return (
    <article className="rp-in relative overflow-hidden rounded-[26px] bg-[var(--parchment-2)] p-7 shadow-[inset_0_0_0_1px_var(--line)] md:p-8">
      <Engraving name={art} className="pointer-events-none absolute -right-6 -top-4 w-36 opacity-[0.08]" />
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="display mb-6 mt-2 text-[38px] leading-none">{title}</h2>
      {children}
    </article>
  );
}

function Stat({ n, label }: { n: ReactNode; label: string }) {
  return (
    <div className="rounded-[16px] bg-[rgba(13,19,56,0.7)] p-4 shadow-[inset_0_0_0_1px_var(--line)]">
      <p className="display text-[36px] leading-none text-[var(--ink)]">{n}</p>
      <p className="mt-1.5 text-[12.5px] text-[var(--text-2)]">{label}</p>
    </div>
  );
}

function Bar({ value }: { value: number }) {
  return (
    <div className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--parchment-3)]">
      <div className="rp-bar h-full origin-left rounded-full bg-[linear-gradient(90deg,var(--ink),var(--gold))]" style={{ width: `${Math.max(2, value * 100)}%` }} />
    </div>
  );
}

/** Six-axis radar drawn as a constellation: stars at each value, joined by a thin line. */
function Radar({ axes }: { axes: { label: string; value: number }[] }) {
  const cx = 150;
  const cy = 140;
  const R = 92;
  const pt = (i: number, r: number) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / axes.length;
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  };
  const poly = axes.map((ax, i) => pt(i, R * Math.max(0.06, ax.value)).join(",")).join(" ");
  return (
    <svg viewBox="0 0 300 290" className="rp-radar w-full" role="img" aria-label={axes.map((a) => `${a.label} ${Math.round(a.value * 100)}`).join(", ")}>
      {[0.25, 0.5, 0.75, 1].map((k) => (
        <polygon key={k} points={axes.map((_, i) => pt(i, R * k).join(",")).join(" ")} fill="none" stroke="var(--line-strong)" strokeWidth="0.75" strokeDasharray={k === 1 ? undefined : "2 4"} />
      ))}
      {axes.map((_, i) => {
        const [x, y] = pt(i, R);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--line)" />;
      })}
      <g className="rp-poly">
        <polygon points={poly} fill="rgba(35,55,165,0.12)" stroke="var(--ink)" strokeWidth="1.2" />
        {axes.map((ax, i) => {
          const [x, y] = pt(i, R * Math.max(0.06, ax.value));
          return <path key={i} d={`M${x} ${y - 6}L${x + 1.6} ${y - 1.6}L${x + 6} ${y}L${x + 1.6} ${y + 1.6}L${x} ${y + 6}L${x - 1.6} ${y + 1.6}L${x - 6} ${y}L${x - 1.6} ${y - 1.6}Z`} fill="var(--gold)" />;
        })}
      </g>
      {axes.map((ax, i) => {
        const [x, y] = pt(i, R + 24);
        return (
          <text key={ax.label} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="10.5" fill="var(--text-2)" fontFamily="var(--sans)">
            {ax.label}
          </text>
        );
      })}
    </svg>
  );
}
