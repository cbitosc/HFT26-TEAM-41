"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "motion/react";
import Chip from "./Chip";
import { Label, Words } from "./fx";

// Screenshots of the running app (frontend/ at localhost:3000), captured with headless
// Chromium on 2026-10-31: a fresh make seed-demo session after one Run, and a submitted
// session's report. If a capture is missing, src is null and the frame says so.
type Shot = { src: string | null; title: string; caption: string; w: number; h: number };

const SHOTS: Shot[] = [
  {
    src: "/shots/ide.webp",
    title: "Candidate IDE",
    caption:
      "The demo task after one Run: 2 of 3 visible tests pass, with the real assertion. Hidden tests are still running in their own sandbox. Tests and config are locked.",
    w: 1440,
    h: 900,
  },
  {
    src: "/shots/report.webp",
    title: "Report",
    caption: "Final score and band, fixed-test counts for visible and hidden tests, regression factor, time, runs, Re-grade.",
    w: 1440,
    h: 470,
  },
];

function Frame({ shot, i }: { shot: Shot; i: number }) {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], i % 2 ? [60, -60] : [30, -30]);
  return (
    <motion.figure ref={ref} className={`shot shot-${i}`} style={{ y: reduce ? 0 : y }}>
      <div className="shot-bar" aria-hidden>
        <i /><i /><i />
        <span>localhost:3000</span>
      </div>
      <div className="shot-img" style={{ aspectRatio: `${shot.w} / ${shot.h}` }}>
        {shot.src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={shot.src} alt={`${shot.title}, running locally`} loading="lazy" width={shot.w} height={shot.h} />
        ) : (
          <span className="shot-missing">Screenshot of the {shot.title.toLowerCase()} goes here</span>
        )}
      </div>
      <figcaption>
        <b>{shot.title}.</b> {shot.caption}
      </figcaption>
    </motion.figure>
  );
}

export default function Product() {
  return (
    <section className="section product" id="product">
      <div className="wrap">
        <div className="grid">
          <div className="product-intro">
            <Label n={5}>The real thing</Label>
            <Words className="h2" text="It runs *today.*" />
            <p>
              Not mock-ups: the candidate IDE and the report from our local stack, on the demo session. The full flow,
              from a fresh session to a re-graded report, is checked end to end by <code>make e2e</code> in headless
              Chromium, with every request that leaves the stack counted as a failure.
            </p>
            <Chip s="built" />
          </div>
        </div>
        <div className="shots">
          {SHOTS.map((s, i) => (
            <Frame key={s.title} shot={s} i={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
