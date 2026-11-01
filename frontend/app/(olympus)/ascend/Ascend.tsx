"use client";

import { useRef, useState, type DragEvent, type ReactNode } from "react";
import { Logo } from "@/components/olympus/Chrome";
import Engraving from "@/components/olympus/Engraving";
import { IconCheck, IconFile, IconUpload, IconX } from "@/components/olympus/Icons";
import { Btn, SmoothScroll } from "@/components/olympus/Kit";
import Meander from "@/components/olympus/Meander";
import { useNav } from "@/components/olympus/Shell";
import { DEMO_PROFILE, handleOf } from "@/lib/olympus/demo";
import { updateJourney, type Candidate } from "@/lib/olympus/journey";
import { gsap, useGsap } from "@/lib/olympus/motion";
import type { Portfolio, Profile } from "@/lib/types";

const STACKS = ["Python", "FastAPI", "Django", "Node.js", "Express", "React", "Next.js", "PostgreSQL", "MongoDB", "Redis", "Docker", "Go", "Java", "PyTorch"];

const PATTERNS: Record<"github" | "leetcode" | "codeforces" | "portfolio", RegExp> = {
  github: /^(https?:\/\/)?(www\.)?github\.com\/[\w-]+\/?$|^[\w-]{1,39}$/i,
  leetcode: /^(https?:\/\/)?(www\.)?leetcode\.com\/(u\/)?[\w-]+\/?$|^[\w-]{1,40}$/i,
  codeforces: /^(https?:\/\/)?(www\.)?codeforces\.com\/profile\/[\w.-]+\/?$|^[\w.-]{1,40}$/i,
  portfolio: /^(https?:\/\/)?[\w-]+(\.[\w-]+)+(\/\S*)?$/i,
};

const STEPS = ["Reading your résumé", "Walking your repositories", "Counting problems by topic", "Choosing your tier", "Forging the trials"];

function toPortfolio(c: Candidate): Portfolio {
  const url = (v: string, base: string) => (v.startsWith("http") ? v : `${base}${handleOf(v)}`);
  const profiles = [
    c.github && { network: "GitHub", username: handleOf(c.github), url: url(c.github, "https://github.com/") },
    c.leetcode && { network: "LeetCode", username: handleOf(c.leetcode), url: url(c.leetcode, "https://leetcode.com/u/") },
    c.codeforces && { network: "Codeforces", username: handleOf(c.codeforces), url: url(c.codeforces, "https://codeforces.com/profile/") },
  ].filter(Boolean) as { network: string; username: string; url: string }[];
  return {
    basics: {
      name: c.name,
      email: c.email || undefined,
      url: c.portfolio ? (c.portfolio.startsWith("http") ? c.portfolio : `https://${c.portfolio}`) : undefined,
      profiles,
    },
    skills: c.stack.length ? [{ name: "Stack", keywords: c.stack }] : [],
    projects: [],
    assessment: { dsaTopicsSolved: {}, githubUrls: profiles.filter((p) => p.network === "GitHub").map((p) => p.url) },
  };
}

export default function Ascend() {
  const { navigate } = useNav();
  const root = useRef<HTMLDivElement>(null);
  const [c, setC] = useState<Candidate>({ name: "", email: "", resumeName: null, github: "", leetcode: "", codeforces: "", portfolio: "", stack: [] });
  const [resumeSize, setResumeSize] = useState(0);
  const [drag, setDrag] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [forging, setForging] = useState(false);
  const [step, setStep] = useState(0);

  const set = <K extends keyof Candidate>(k: K, v: Candidate[K]) => setC((prev) => ({ ...prev, [k]: v }));
  const valid = (k: keyof typeof PATTERNS) => !c[k] || PATTERNS[k].test(c[k].trim());
  const offered = [!!c.resumeName, !!c.github, !!c.leetcode, !!c.codeforces, !!c.portfolio].filter(Boolean).length;
  const ready = c.name.trim().length > 1 && offered >= 1 && (["github", "leetcode", "codeforces", "portfolio"] as const).every(valid);

  useGsap(root, (reduced) => {
    if (reduced) return;
    gsap.from(".asc-in", { y: 50, opacity: 0, duration: 1.3, stagger: 0.07, ease: "expo.out", delay: 0.2 });
    gsap.from(".asc-hermes", { x: -120, y: 60, rotate: -8, opacity: 0, duration: 2, ease: "expo.out", delay: 0.3 });
    gsap.to(".asc-hermes-float", { y: -18, rotate: 1.5, duration: 3.2, ease: "sine.inOut", yoyo: true, repeat: -1 });
  });

  const takeFile = (f: File | undefined) => {
    if (!f) return;
    set("resumeName", f.name);
    setResumeSize(f.size);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    takeFile(e.dataTransfer.files[0]);
  };

  const submit = async () => {
    if (!ready) return;
    setForging(true);
    const ticker = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 700);
    let profile: Profile = DEMO_PROFILE;
    let assessmentId: string | null = null;
    let offline = true;
    try {
      const res = await fetch("/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ portfolio: toPortfolio(c) }),
      });
      if (res.ok) {
        const data = (await res.json()) as { assessment_id: string; profile: Profile };
        profile = data.profile;
        assessmentId = data.assessment_id;
        offline = false;
      }
    } catch {
      // API unreachable: continue with the demo profile
    }
    await new Promise((r) => setTimeout(r, 3600));
    window.clearInterval(ticker);
    updateJourney({ candidate: c, profile, assessmentId, offline, trials: null, labyrinth: null, oracle: null, reportAt: null });
    navigate("/trials");
  };

  return (
    <div ref={root} className="relative min-h-screen">
      <SmoothScroll />
      <header className="fixed inset-x-0 top-0 z-40 flex items-center justify-between px-[var(--gutter)] py-6">
        <Logo />
        <span className="eyebrow hidden sm:block">Round Ⅰ of Ⅴ · The Offering</span>
      </header>

      <div className="mx-auto grid max-w-[1600px] gap-12 px-[var(--gutter)] pt-32 pb-24 lg:grid-cols-[0.95fr_1.05fr] lg:gap-20">
        {/* Left: the invitation */}
        <aside className="lg:sticky lg:top-28 lg:h-[calc(100vh-9rem)] lg:self-start">
          <div className="flex h-full flex-col">
            <p className="eyebrow asc-in mb-6 flex items-center gap-3">
              <span className="numeral text-[18px] normal-case tracking-normal text-[var(--ink)]">Ⅰ</span> The Offering
            </p>
            <h1 className="display asc-in text-[clamp(52px,6.4vw,112px)]">
              Lay your scrolls <em className="text-[var(--ink)]">at the gate.</em>
            </h1>
            <p className="asc-in mt-6 max-w-[460px] text-[17px] leading-relaxed text-[var(--text-2)]">
              Hermes carries what you offer to the Oracle. From it we forge a trial in your own stack, matched to the problems you have
              actually solved. Public links only; nothing is posted anywhere.
            </p>
            <div className="relative mt-8 hidden min-h-[260px] flex-1 lg:block">
              <div className="asc-hermes absolute bottom-0 left-[-2%] top-0">
                <div className="asc-hermes-float h-full">
                  <Engraving name="hermes-flight" fade className="h-full max-w-[min(30vw,400px)] opacity-50" style={{ width: "auto" }} label="Hermes in flight" />
                </div>
              </div>
              <div className="absolute bottom-[4%] right-[6%] h-[38%]">
                <Engraving name="scroll" fade className="h-full opacity-35" style={{ width: "auto" }} />
              </div>
            </div>
          </div>
        </aside>

        {/* Right: the offering form */}
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <Section n="i" title="Who ascends">
            <div className="grid gap-6 sm:grid-cols-2">
              <Field id="name" label="Full name" value={c.name} onChange={(v) => set("name", v)} autoComplete="name" />
              <Field id="email" label="Email (optional)" type="email" value={c.email} onChange={(v) => set("email", v)} autoComplete="email" />
            </div>
          </Section>

          <Section n="ii" title="Your résumé">
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              data-cursor="Drop"
              className="group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[20px] px-6 py-12 text-center transition-colors duration-500"
              style={{ background: drag ? "rgba(35,55,165,0.08)" : "rgba(35,55,165,0.03)" }}
            >
              <DashedBorder active={drag || !!c.resumeName} />
              <input type="file" accept=".pdf,.doc,.docx" className="sr-only" onChange={(e) => takeFile(e.target.files?.[0])} />
              {c.resumeName ? (
                <div className="rise flex w-full max-w-[420px] items-center gap-4 rounded-2xl bg-[var(--parchment)] p-4 text-left shadow-[inset_0_0_0_1px_var(--line-strong)]">
                  <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-[var(--ink)] text-[var(--parchment)]">
                    <IconFile size={20} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{c.resumeName}</span>
                    <span className="mono text-[12px] text-[var(--text-3)]">{(resumeSize / 1024).toFixed(0)} KB · ready</span>
                  </span>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Remove résumé"
                    onClick={(e) => {
                      e.preventDefault();
                      set("resumeName", null);
                    }}
                  >
                    <IconX size={16} />
                  </button>
                </div>
              ) : (
                <>
                  <span className="mb-5 grid h-16 w-16 place-items-center rounded-full bg-[var(--ink)] text-[var(--parchment)] transition-transform duration-700 group-hover:-translate-y-1 group-hover:rotate-[-8deg]">
                    <IconUpload size={22} />
                  </span>
                  <span className="display text-[30px]">Drop your résumé here</span>
                  <span className="mt-2 text-[14px] text-[var(--text-2)]">or click to choose · PDF or Word · up to 5 MB</span>
                </>
              )}
            </label>
          </Section>

          <Section n="iii" title="Your record">
            <div className="grid gap-6 sm:grid-cols-2">
              <Field
                id="github"
                label="GitHub profile"
                seal="GH"
                value={c.github}
                onChange={(v) => set("github", v)}
                onBlur={() => setTouched((t) => ({ ...t, github: true }))}
                invalid={touched.github && !valid("github")}
                hint={touched.github && !valid("github") ? "Use github.com/you or just your username" : "Repositories, languages and topics"}
              />
              <Field
                id="leetcode"
                label="LeetCode profile"
                seal="LC"
                value={c.leetcode}
                onChange={(v) => set("leetcode", v)}
                onBlur={() => setTouched((t) => ({ ...t, leetcode: true }))}
                invalid={touched.leetcode && !valid("leetcode")}
                hint={touched.leetcode && !valid("leetcode") ? "Use leetcode.com/u/you or your username" : "Problems solved by topic"}
              />
              <Field
                id="codeforces"
                label="Codeforces handle"
                seal="CF"
                value={c.codeforces}
                onChange={(v) => set("codeforces", v)}
                onBlur={() => setTouched((t) => ({ ...t, codeforces: true }))}
                invalid={touched.codeforces && !valid("codeforces")}
                hint={touched.codeforces && !valid("codeforces") ? "Use codeforces.com/profile/you or your handle" : "Rating and contest history"}
              />
              <Field
                id="portfolio"
                label="Portfolio website"
                seal="www"
                value={c.portfolio}
                onChange={(v) => set("portfolio", v)}
                onBlur={() => setTouched((t) => ({ ...t, portfolio: true }))}
                invalid={touched.portfolio && !valid("portfolio")}
                hint={touched.portfolio && !valid("portfolio") ? "Enter a site such as you.dev" : "Projects you'd like us to read"}
              />
            </div>
          </Section>

          <Section n="iv" title="Your stack" note="Optional — sharpens the trial">
            <div className="flex flex-wrap gap-2">
              {STACKS.map((s) => {
                const on = c.stack.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={on}
                    onClick={() => set("stack", on ? c.stack.filter((x) => x !== s) : [...c.stack, s])}
                    className="chip transition-all duration-300 hover:-translate-y-0.5"
                    style={on ? { background: "var(--ink)", color: "var(--parchment)", boxShadow: "none" } : undefined}
                  >
                    {on && <IconCheck size={12} strokeWidth={2.2} />}
                    {s}
                  </button>
                );
              })}
            </div>
          </Section>

          <div className="asc-in flex flex-wrap items-center justify-between gap-6 rounded-[24px] bg-[var(--parchment-2)] p-6 shadow-[inset_0_0_0_1px_var(--line)] md:p-8">
            <div className="flex items-center gap-5">
              <SealProgress count={offered} />
              <div>
                <p className="display text-[26px] leading-tight">
                  {offered === 0 ? "Nothing offered yet" : `${offered} of 5 scrolls offered`}
                </p>
                <p className="text-[14px] text-[var(--text-2)]">
                  {c.name.trim().length > 1 ? "The more you offer, the closer the trial fits." : "Add your name and at least one scroll."}
                </p>
              </div>
            </div>
            <Btn type="submit" disabled={!ready || forging}>
              Consult the Oracle
            </Btn>
          </div>
        </form>
      </div>

      {forging && <ForgeOverlay step={step} name={c.name} />}
    </div>
  );
}

function Section({ n, title, note, children }: { n: string; title: string; note?: string; children: ReactNode }) {
  return (
    <section className="asc-in rounded-[24px] bg-[rgba(13,19,56,0.55)] p-6 shadow-[inset_0_0_0_1px_var(--line)] md:p-8">
      <div className="mb-5 flex items-baseline justify-between gap-4">
        <h2 className="flex items-baseline gap-3 text-[18px] font-medium">
          <span className="numeral text-[20px] text-[var(--ink)]">{n}.</span>
          {title}
        </h2>
        {note && <span className="text-[13px] text-[var(--text-3)]">{note}</span>}
      </div>
      {children}
    </section>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  onBlur,
  hint,
  invalid,
  seal,
  type = "text",
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  hint?: string;
  invalid?: boolean;
  seal?: string;
  type?: string;
  autoComplete?: string;
}) {
  return (
    <div className="flex items-start gap-4">
      {seal && (
        <span
          className="mono mt-5 grid h-11 w-11 shrink-0 place-items-center rounded-full text-[11px] font-semibold transition-colors duration-500"
          style={value ? { background: "var(--ink)", color: "var(--parchment)" } : { boxShadow: "inset 0 0 0 1px var(--line-strong)", color: "var(--text-2)" }}
          aria-hidden="true"
        >
          {seal}
        </span>
      )}
      <div className={`field flex-1 ${invalid ? "is-invalid" : ""}`}>
        <input
          id={id}
          type={type}
          value={value}
          placeholder=" "
          autoComplete={autoComplete}
          aria-invalid={invalid || undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
        />
        <label htmlFor={id}>{label}</label>
        {hint && (
          <span id={`${id}-hint`} className="field-hint">
            {hint}
          </span>
        )}
      </div>
    </div>
  );
}

function DashedBorder({ active }: { active: boolean }) {
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
      <rect
        x="1"
        y="1"
        width="calc(100% - 2px)"
        height="calc(100% - 2px)"
        rx="19"
        fill="none"
        stroke="var(--ink)"
        strokeOpacity={active ? 0.8 : 0.35}
        strokeWidth="1.2"
        strokeDasharray="6 8"
        style={{ animation: "oly-dash 18s linear infinite" }}
      />
      <style>{`@keyframes oly-dash { to { stroke-dashoffset: -280; } }`}</style>
    </svg>
  );
}

function SealProgress({ count }: { count: number }) {
  const r = 26;
  const len = 2 * Math.PI * r;
  return (
    <div className="relative grid h-[68px] w-[68px] place-items-center">
      <svg viewBox="0 0 64 64" className="absolute inset-0 -rotate-90">
        <circle cx="32" cy="32" r={r} fill="none" stroke="var(--line-strong)" strokeWidth="1.5" />
        <circle
          cx="32"
          cy="32"
          r={r}
          fill="none"
          stroke="var(--ink)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={len}
          strokeDashoffset={len * (1 - count / 5)}
          style={{ transition: "stroke-dashoffset 0.9s var(--ease-out)" }}
        />
      </svg>
      <Engraving name="wreath" className="w-8 text-[var(--ink)]" />
    </div>
  );
}

function ForgeOverlay({ step, name }: { step: number; name: string }) {
  const el = useRef<HTMLDivElement>(null);
  useGsap(el, (reduced) => {
    if (reduced) return;
    gsap.fromTo(el.current, { clipPath: "circle(0% at 50% 100%)" }, { clipPath: "circle(150% at 50% 100%)", duration: 1.3, ease: "expo.inOut" });
    gsap.from(".fo-in", { y: 30, opacity: 0, duration: 1.1, stagger: 0.1, delay: 0.6, ease: "expo.out" });
  });
  return (
    <div ref={el} className="oly-night fixed inset-0 z-[120] grid place-items-center overflow-hidden px-6" role="status" aria-live="polite">
      <div className="pointer-events-none absolute left-1/2 top-1/2 w-[min(110vw,980px)] -translate-x-1/2 -translate-y-1/2 opacity-[0.12]" aria-hidden="true">
        <div className="spin-mid">
          <Engraving name="starchart-1" className="w-full" style={{ color: "var(--moon)" }} />
        </div>
      </div>
      <Meander className="absolute inset-x-0 top-8 text-[var(--moon)] opacity-20" height={14} />
      <div className="relative w-full max-w-[560px] text-center">
        <p className="eyebrow fo-in mb-6">The Oracle is reading</p>
        <h2 className="display fo-in text-[clamp(44px,6vw,84px)]">
          Patience, <em style={{ color: "var(--gold-bright)" }}>{name.split(" ")[0] || "traveller"}</em>.
        </h2>
        <ol className="fo-in mx-auto mt-10 max-w-[360px] space-y-3 text-left">
          {STEPS.map((s, i) => (
            <li key={s} className="flex items-center gap-4 text-[15px] transition-opacity duration-500" style={{ opacity: i <= step ? 1 : 0.3 }}>
              <span
                className="grid h-6 w-6 shrink-0 place-items-center rounded-full"
                style={{ background: i < step ? "var(--gold-bright)" : "transparent", boxShadow: i < step ? "none" : "inset 0 0 0 1px rgba(233,228,212,0.35)", color: "var(--night)" }}
              >
                {i < step ? <IconCheck size={12} strokeWidth={2.4} /> : i === step ? <span className="pulse-dot text-[var(--gold-bright)]" /> : null}
              </span>
              <span className={i === step ? "shimmer" : ""}>{s}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
