"use client";

// Landing: Areté as a set of engraved plates on the night stage. The hero is Athena under a
// turning astrolabe with the name in front of her (from the showcase's Assay hero). Each
// plate below shows one capability of the product with a small mock of its real UI, under
// one engraving. Motion is scroll-driven only (parallax and reveals); no cursor effects.
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { BRAND, SiteNav } from "@/components/olympus/Chrome";
import Greek from "@/components/olympus/Greek";
import { IconCheck } from "@/components/olympus/Icons";
import { Btn, SmoothScroll } from "@/components/olympus/Kit";
import Meander from "@/components/olympus/Meander";
import { TLink } from "@/components/olympus/Shell";
import type { GreekName } from "@/lib/olympus/greek";
import { gsap, ScrollTrigger, useGsap } from "@/lib/olympus/motion";
import "./landing.css";

const NUMERALS = ["I", "II", "III", "IV", "V"];

const BAND = [
  "Your own stack",
  "Your own projects",
  "Sixty minutes",
  "Validated before it ships",
  "Sandboxed, network off",
  "Graded by tests alone",
  "Re-graded to the byte",
];

type Step = { title: string; room: string; href: string; art: GreekName; ink?: string; body: string; mock: React.ReactNode };

const STEPS: Step[] = [
  {
    room: "The Offering",
    title: "Your portfolio, read by rules.",
    href: "/ascend",
    art: "hermes-fly",
    body: "Upload a résumé or link GitHub, LeetCode and Codeforces. Hermes carries it all into one portfolio, and plain rules pick the domain, language, concepts and tier.",
    mock: (
      <>
        <div className="flex flex-wrap gap-1.5">
          {["résumé.pdf", "github.com/ananyarao", "LeetCode 214 solved", "Codeforces 1480"].map((c) => (
            <span key={c} className="tag">
              {c}
            </span>
          ))}
        </div>
        <Code>
          <K>domain</K> backend <K>runtime</K> python311
          <br />
          <K>concepts</K> pagination, caching <K>tier</K> adept
        </Code>
      </>
    ),
  },
  {
    room: "Trials of Athena",
    title: "Sixty minutes in your own stack.",
    href: "/trials",
    art: "helmet",
    body: "A bug or a missing feature in a repo shaped like yours, plus an algorithm matched to the topics you have solved. Every run is a sealed sandbox; hints climb a ladder and never write the fix.",
    mock: (
      <>
        <ul className="mock-list">
          <li>
            <span>Fix: expense list pages are wrong</span>
            <span className="text-[var(--text-3)]">app/utils.py</span>
          </li>
          <li>
            <span>Longest run of distinct characters</span>
            <span className="text-[var(--text-3)]">sliding window</span>
          </li>
        </ul>
        <Code>
          <span className="text-[var(--text-3)]">$</span> run visible <span className="text-[var(--pass)]">3 passed</span> in 2.6 s
        </Code>
        <div className="flex gap-1.5">
          {["L1 concept", "L2 function", "L3 line"].map((l) => (
            <span key={l} className="tag">
              {l}
            </span>
          ))}
        </div>
      </>
    ),
  },
  {
    room: "The Labyrinth",
    title: "Read code you didn't write.",
    href: "/labyrinth",
    art: "bull",
    ink: "var(--moon)",
    body: "A real repository with real issues. Find each cause, explain the fix and say how you'd make it faster. Ariadne holds the thread: she points the way and never walks it.",
    mock: (
      <ul className="mock-list">
        <li>
          <span>#12 East-zone couriers get far parcels</span>
          <span className="text-[var(--fail)]">bug</span>
        </li>
        <li>
          <span>#15 Route cache serves another zone</span>
          <span className="text-[var(--fail)]">bug</span>
        </li>
        <li>
          <span>#18 GET /deliveries takes 4 s</span>
          <span className="text-[var(--gold-bright)]">performance</span>
        </li>
      </ul>
    ),
  },
  {
    room: "The Oracle",
    title: "Explain it, out loud.",
    href: "/oracle",
    art: "sun",
    body: "A short voice interview with an AI that has read the role, your project and your own diff. One follow-up per question, never about who you are, and never part of the score.",
    mock: (
      <div className="space-y-2 text-[13.5px]">
        <p>
          <span className="text-[var(--ink)]">Oracle</span> Which function did you change, and why?
        </p>
        <p className="text-[var(--text-2)]">
          <span className="text-[var(--text)]">You</span> paginate computed the offset from page minus two…
        </p>
        <p className="tag !text-[var(--gold-bright)]">4 of 4 submission facts mentioned</p>
      </div>
    ),
  },
  {
    room: "The Verdict",
    title: "A score you can recompute.",
    href: "/verdict",
    art: "wreath",
    ink: "var(--gold-bright)",
    body: "Correctness comes from hidden tests and published formulas; re-grade gives the identical number. Beside it, never in it: a Trail Map of how you moved through the code, a portfolio claim check and integrity notes.",
    mock: (
      <div className="flex flex-wrap items-end gap-6">
        <div>
          <p className="display text-[64px] leading-none text-[var(--gold-bright)]">100</p>
          <p className="text-[13px] text-[var(--text-2)]">Strong</p>
        </div>
        <ul className="space-y-1.5 text-[13.5px]">
          {["hidden tests 92 of 92", "re-grade identical", "claims checked: pagination, sliding window"].map((t) => (
            <li key={t} className="flex items-center gap-2">
              <Tick /> {t}
            </li>
          ))}
        </ul>
      </div>
    ),
  },
];

const GUIDES: { name: string; role: string; art: GreekName; body: string; rule: string }[] = [
  {
    name: "Hermes",
    role: "Hint assistant",
    art: "hermes",
    body: "Concept, then function, then line, rising only after you run the tests. Eight hints per task; asking for the answer gets a refusal, not a model call.",
    rule: "Never writes your fix",
  },
  {
    name: "Apollo",
    role: "Report summary",
    art: "apollo",
    body: "Four sentences for the recruiter, written from the report's numbers alone: no code, no tests, no guessing at causes.",
    rule: "Labelled “AI summary, not scored”",
  },
  {
    name: "Pythia",
    role: "Voice interviewer",
    art: "sun",
    body: "Speaks with a generated voice, listens through the browser, follows up once, and stops at the time limit.",
    rule: "Shown in the report, never scored",
  },
];

const RULES = [
  ["No model decides a score", "Correctness comes only from test results and published formulas."],
  ["What is hidden stays hidden", "Reference solutions and hidden tests never reach the browser or any model."],
  ["Every run in a sealed vault", "A fresh container per run: no network, capped CPU, memory and time, non-root."],
  ["Same deeds, same verdict", "The same events and snapshots always give the same score, to the byte."],
];

export default function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useGsap(root, (reduced) => {
    if (reduced) return;

    // Hero: one intro, then scroll parallax (Athena rises, the name sinks, the sky turns).
    gsap
      .timeline({ defaults: { ease: "expo.out" } })
      .from(".hero-astro-in", { opacity: 0, scale: 0.86, rotate: -30, duration: 2.2 })
      .from(".hero-athena-in", { opacity: 0, y: 90, duration: 1.7 }, 0.1)
      .from(".hero-ch > span", { yPercent: 105, duration: 1.3, stagger: 0.07 }, 0.25)
      .from(".hero-fade", { opacity: 0, y: 24, duration: 1, stagger: 0.12 }, 0.7);
    const hero = { trigger: ".hero", start: "top top", end: "bottom top", scrub: true };
    gsap.to(".hero-athena", { yPercent: -16, ease: "none", scrollTrigger: hero });
    gsap.to(".hero-name", { yPercent: 36, ease: "none", scrollTrigger: hero });
    gsap.to(".hero-astro", { rotate: 40, scale: 1.2, ease: "none", scrollTrigger: hero });
    gsap.to(".hero-top", { opacity: 0, yPercent: -30, ease: "none", scrollTrigger: { ...hero, end: "60% top" } });

    // Band: a slow marquee.
    gsap.to(".band-track", { xPercent: -50, duration: 40, ease: "none", repeat: -1 });

    // Plates: the figure on the stage follows the step in the middle of the screen.
    gsap.utils.toArray<HTMLElement>(".step").forEach((el, i) => {
      ScrollTrigger.create({ trigger: el, start: "top 55%", end: "bottom 55%", onToggle: (s) => s.isActive && setActive(i) });
    });
    gsap.to(".stage-art", { yPercent: -8, ease: "none", scrollTrigger: { trigger: ".journey", start: "top bottom", end: "bottom top", scrub: true } });

    // Atlas carries the gate; the tier columns rise as they come in.
    gsap.fromTo(".atlas-fig", { yPercent: 12 }, { yPercent: -10, ease: "none", scrollTrigger: { trigger: ".forge", start: "top bottom", end: "bottom top", scrub: true } });
    gsap.from(".tier-col", { yPercent: 40, opacity: 0, stagger: 0.12, ease: "none", scrollTrigger: { trigger: ".tiers", start: "top 90%", end: "top 45%", scrub: true } });

    // The aegis turns while the rules pass; the ship crosses the practice band.
    gsap.fromTo(".aegis", { rotate: -25, scale: 0.9 }, { rotate: 25, scale: 1.05, ease: "none", scrollTrigger: { trigger: ".rules", start: "top bottom", end: "bottom top", scrub: true } });
    gsap.fromTo(".ship", { xPercent: -60 }, { xPercent: 60, ease: "none", scrollTrigger: { trigger: ".practice", start: "top bottom", end: "bottom top", scrub: true } });
    gsap.fromTo(".finale-temple", { yPercent: 25 }, { yPercent: 0, ease: "none", scrollTrigger: { trigger: ".finale", start: "top bottom", end: "bottom bottom", scrub: true } });

    // Everything marked .reveal rises in once.
    ScrollTrigger.batch(".reveal", {
      start: "top 88%",
      once: true,
      onEnter: (els) => gsap.fromTo(els, { opacity: 0, y: 36 }, { opacity: 1, y: 0, duration: 1.1, stagger: 0.1, ease: "expo.out" }),
    });
  });

  return (
    <div ref={root} className="landing">
      <SmoothScroll />
      <SiteNav />

      {/* ---------------------------------------------------------------- Hero */}
      <section className="hero" id="top">
        <div className="hero-stage" aria-hidden="true">
          <div className="hero-astro">
            <div className="hero-astro-in">
              <Astrolabe />
            </div>
          </div>
          <div className="hero-athena">
            <div className="hero-athena-in">
              <Greek name="athena" eager />
            </div>
          </div>
          <div className="hero-floor" />
        </div>
        <h1 className="hero-name display" aria-label={BRAND}>
          {BRAND.split("").map((ch, i) => (
            <span key={i} className="hero-ch" aria-hidden="true">
              <span>{ch}</span>
            </span>
          ))}
        </h1>

        <div className="hero-top">
          <div className="hero-copy">
            <p className="hero-promise hero-fade display">
              A coding assessment built from the candidate&apos;s <em>own</em> portfolio, and graded only by tests.
            </p>
            <p className="hero-sub hero-fade">
              Upload a portfolio. Get a 60-minute task in the candidate&apos;s stack and domain, validated in a sandbox before
              anyone sees it. The score comes from test results and fixed formulas, and you can recompute it.
            </p>
            <div className="hero-fade mt-7 flex flex-wrap gap-3">
              <Btn href="/ascend">Start with a portfolio</Btn>
              <a href="#journey" className="btn btn-ghost">
                <span className="btn-label">
                  <span>See the five plates</span>
                  <span aria-hidden="true">See the five plates</span>
                </span>
              </a>
            </div>
          </div>
          <aside className="hero-plate hero-fade">
            <p className="inscr">Plate I, Athena</p>
            <p>
              In the Eumenides, Athena ends a blood feud by founding the first court: evidence is heard, votes are counted,
              and nobody&apos;s anger decides. We built the same thing for code.
            </p>
            <p className="inscr text-[var(--gold-bright)]">CBIT Hacktoberfest &apos;26, Team XLI</p>
          </aside>
        </div>
      </section>

      {/* ---------------------------------------------------------------- Band */}
      <section className="band" aria-label="What Areté promises">
        <Meander className="text-[var(--ink)] opacity-40" height={12} />
        <div className="band-row display" aria-hidden="true">
          <div className="band-track">
            {[...BAND, ...BAND].map((w, i) => (
              <span key={i}>
                {w}
                <i>✦</i>
              </span>
            ))}
          </div>
        </div>
        <Meander className="text-[var(--ink)] opacity-40" height={12} />
      </section>

      {/* ---------------------------------------------------------------- Journey */}
      <section className="journey" id="journey">
        <div className="journey-head reveal">
          <p className="inscr">The journey</p>
          <h2 className="display">Five plates, one honest report.</h2>
          <p>Each room tests something a résumé can only claim: that you can read, repair, reason and explain.</p>
        </div>
        <div className="journey-grid">
          <div className="stage" aria-hidden="true">
            <div className="stage-in">
              <div className="stage-art">
                {STEPS.map((s, i) => (
                  <div key={s.room} className={`stage-fig ${i === active ? "is-on" : ""}`} style={{ color: s.ink }}>
                    {/* Enclosed shapes (medallion, wreath) as line work: their porcelain fill reads as a disk. */}
                    <Greek name={s.art} ink={!!s.ink} />
                  </div>
                ))}
              </div>
              <p className="stage-num display">
                <span>Plate</span> {NUMERALS[active]}
              </p>
            </div>
          </div>
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s.room} className={`step ${i === active ? "is-on" : ""}`}>
                <p className="inscr">
                  {NUMERALS[i]}. {s.room}
                </p>
                <h3 className="display">{s.title}</h3>
                <p className="step-body">{s.body}</p>
                <div className="mock">{s.mock}</div>
                <TLink href={s.href} className="step-link">
                  Open {s.room}
                </TLink>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ---------------------------------------------------------------- Forge */}
      <section className="forge" id="forge">
        <div className="forge-grid">
          <div className="atlas-wrap" aria-hidden="true">
            <div className="atlas-fig">
              <Greek name="atlas" />
            </div>
          </div>
          <div>
            <p className="inscr reveal">How tasks are forged</p>
            <h2 className="display reveal">Atlas carries every task through the gate before you see it.</h2>
            <p className="lede reveal">
              A seed repository is mutated in your language, then held until it proves itself fair. Nothing reaches a
              candidate on a model&apos;s word.
            </p>
            <ul className="gate reveal">
              {[
                ["Reference passes", "every test, three runs in a row"],
                ["Starter fails", "at least one visible test"],
                ["Statement checked", "it doesn't give the fix away"],
                ["Algorithm stubs", "a blank answer fails most cases"],
                ["Tests have teeth", "mutation score on the reference"],
              ].map(([a, b]) => (
                <li key={a}>
                  <Tick /> <span className="text-[var(--text)]">{a}</span> <span className="text-[var(--text-2)]">{b}</span>
                </li>
              ))}
            </ul>
            <div className="tiers">
              {(
                [
                  ["Novice", "ionic", "1-file bug fix, easy algorithm", "55%"],
                  ["Adept", "corinthian", "2–3 file feature, medium, hints on", "75%"],
                  ["Master", "column", "multi-file bug, speed budget, hard", "100%"],
                ] as [string, GreekName, string, string][]
              ).map(([t, art, d, h]) => (
                <div key={t} className="tier-col">
                  <div className="tier-art" style={{ height: h }}>
                    <Greek name={art} ink />
                  </div>
                  <p className="display text-[30px]">{t}</p>
                  <p className="text-[13px] leading-snug text-[var(--text-2)]">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- Guides */}
      <section className="guides" id="guides">
        <div className="section-head reveal">
          <p className="inscr">The pantheon</p>
          <h2 className="display">Three AI helpers, each with one job and one rule.</h2>
        </div>
        <div className="guide-grid">
          {GUIDES.map((g) => (
            <article key={g.name} className="guide reveal">
              <div className="guide-art">
                <Greek name={g.art} />
              </div>
              <h3 className="display">{g.name}</h3>
              <p className="inscr">{g.role}</p>
              <p className="guide-body">{g.body}</p>
              <p className="guide-rule">{g.rule}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------- Rules */}
      <section className="rules" id="rules">
        <div className="aegis-wrap" aria-hidden="true">
          <div className="aegis">
            <Greek name="aegis" ink />
          </div>
        </div>
        <div className="rules-in">
          <div className="section-head reveal">
            <p className="inscr">The laws</p>
            <h2 className="display">Medusa&apos;s gaze can&apos;t be flattered. Neither can the grader.</h2>
          </div>
          <dl className="rule-grid">
            {RULES.map(([t, d], i) => (
              <div key={t} className="rule reveal">
                <span className="display rule-n">{NUMERALS[i]}</span>
                <dt>{t}</dt>
                <dd>{d}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ---------------------------------------------------------------- Practice */}
      <section className="practice" id="practice">
        <div className="practice-sea" aria-hidden="true">
          <div className="ship">
            <Greek name="ship" ink />
          </div>
        </div>
        <div className="practice-in reveal">
          <div>
            <p className="inscr">Before the voyage</p>
            <h2 className="display">Practise first, no sign-up.</h2>
          </div>
          <div>
            <p className="lede">
              A problem list with a full editor: run with your own input, then submit against hidden cases in Python or
              JavaScript. Practice problems never appear in an assessment.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/practice" className="btn">
                <span className="btn-label">
                  <span>Open practice</span>
                  <span aria-hidden="true">Open practice</span>
                </span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- Finale */}
      <section className="finale">
        <div className="finale-in">
          <h2 className="display finale-word">Ascend.</h2>
          <p className="lede">Five rooms, about ninety minutes, one report you can recompute. Bring your scrolls.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Btn href="/ascend">Start with a portfolio</Btn>
          </div>
        </div>
        <div className="finale-temple" aria-hidden="true">
          <Greek name="parthenon" ink />
        </div>
        <footer className="foot">
          <span className="display text-[24px] text-[var(--text)]">{BRAND}</span>
          <nav className="flex flex-wrap gap-6">
            {[
              ["/ascend", "Offering"],
              ["/trials", "Trials"],
              ["/labyrinth", "Labyrinth"],
              ["/oracle", "Oracle"],
              ["/verdict", "Verdict"],
            ].map(([href, label]) => (
              <TLink key={href} href={href} className="hover:text-[var(--text)]">
                {label}
              </TLink>
            ))}
          </nav>
          <span>Scores come from tests, never from a model.</span>
        </footer>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- pieces

function K({ children }: { children: React.ReactNode }) {
  return <span className="text-[var(--ink)]">{children} </span>;
}

function Code({ children }: { children: React.ReactNode }) {
  return <div className="code">{children}</div>;
}

function Tick() {
  return (
    <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-[var(--pass)]/20 text-[var(--pass)]">
      <IconCheck size={10} strokeWidth={2.4} />
    </span>
  );
}

function rng(seed: number) {
  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

const RING_TEXT =
  "The candidate’s own work ✦ in their own stack ✦ checked before anyone sees it ✦ graded by tests alone ✦ re-graded to the byte ✦ ";

/** Athena's halo: a turning astrolabe with an inscribed ring and constellations (from the showcase). */
function Astrolabe() {
  const { ticks, stars, lines } = useMemo(() => {
    const r = rng(41);
    const ticks = Array.from({ length: 360 }, (_, i) => {
      const a = (i * Math.PI) / 180;
      const len = i % 30 === 0 ? 26 : i % 5 === 0 ? 14 : 7;
      return [470, 470, 470 - len, 470 - len].map((d, k) => +((k % 2 ? Math.sin(a) : Math.cos(a)) * d).toFixed(2));
    });
    const stars = Array.from({ length: 90 }, () => {
      const a = r() * Math.PI * 2;
      const d = 60 + Math.sqrt(r()) * 330;
      return [+(Math.cos(a) * d).toFixed(1), +(Math.sin(a) * d).toFixed(1), +(0.7 + r() * 1.9).toFixed(2)];
    });
    const lines: string[] = [];
    for (let k = 0; k < 9; k++) {
      let cur = stars[Math.floor(r() * stars.length)];
      let d = `M${cur[0].toFixed(1)} ${cur[1].toFixed(1)}`;
      const used = new Set([cur]);
      for (let s = 0; s < 3 + Math.floor(r() * 3); s++) {
        const next = stars
          .filter((p) => !used.has(p))
          .sort((a, b) => Math.hypot(a[0] - cur[0], a[1] - cur[1]) - Math.hypot(b[0] - cur[0], b[1] - cur[1]))[0];
        if (!next || Math.hypot(next[0] - cur[0], next[1] - cur[1]) > 120) break;
        used.add(next);
        cur = next;
        d += ` L${cur[0].toFixed(1)} ${cur[1].toFixed(1)}`;
      }
      lines.push(d);
    }
    return { ticks, stars, lines };
  }, []);

  return (
    <svg viewBox="-500 -500 1000 1000" className="astro">
      <defs>
        <path id="ring-path" d="M0,-428 a428,428 0 1,1 -0.1,0" />
      </defs>
      <g className="astro-spin">
        <circle r="470" className="a-line" />
        <circle r="404" className="a-line" />
        <circle r="452" className="a-line a-faint" />
        {ticks.map(([x1, y1, x2, y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className="a-tick" />
        ))}
        <text className="a-text">
          <textPath href="#ring-path">{RING_TEXT + RING_TEXT}</textPath>
        </text>
      </g>
      <g className="astro-spin-rev">
        <circle r="330" className="a-line a-dash" />
        <circle r="210" className="a-line a-faint" />
        {Array.from({ length: 12 }, (_, i) => {
          const a = (i * Math.PI) / 6;
          return (
            <line
              key={i}
              x1={+(Math.cos(a) * 210).toFixed(2)}
              y1={+(Math.sin(a) * 210).toFixed(2)}
              x2={+(Math.cos(a) * 404).toFixed(2)}
              y2={+(Math.sin(a) * 404).toFixed(2)}
              className="a-line a-faint"
            />
          );
        })}
        {lines.map((d, i) => (
          <path key={i} d={d} className="a-const" />
        ))}
        {stars.map(([x, y, s], i) => (
          <circle key={i} cx={x} cy={y} r={s} className="a-star" />
        ))}
      </g>
    </svg>
  );
}
