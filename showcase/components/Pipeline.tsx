"use client";

import { useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "motion/react";
import { STAGES } from "@/lib/site";
import { NUMERALS, type GreekName } from "@/lib/greek";
import { ARTIFACTS } from "./Artifacts";
import Chip from "./Chip";
import { Engraving, Label, Words } from "./fx";

// The voyage. Desktop: a tall track with a sticky frame; scroll position picks the
// port, the ship sails the route along the bottom, Pegasus crosses on the way in.
// Phones: the same stages as a plain list with each artifact inline.

const EMBLEM: Record<string, GreekName> = {
  portfolio: "scroll",
  profile: "compass",
  tasks: "amphora",
  gate: "arch",
  ide: "torch",
  assistant: "helmet",
  report: "wreath",
};

function Flyby() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const x = useTransform(scrollYProgress, [0, 1], ["-40vw", "120vw"]);
  const y = useTransform(scrollYProgress, [0, 0.5, 1], ["30%", "-10%", "-50%"]);
  const rotate = useTransform(scrollYProgress, [0, 1], [8, -6]);
  if (reduce) return null;
  return (
    <div className="flyby" ref={ref} aria-hidden>
      <motion.div className="flyby-horse" style={{ x, y, rotate }}>
        <Engraving name="pegasus" />
      </motion.div>
    </div>
  );
}

export default function Pipeline() {
  const track = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const { scrollYProgress } = useScroll({ target: track, offset: ["start start", "end end"] });
  const sail = useSpring(scrollYProgress, { stiffness: 90, damping: 24 });
  const shipX = useTransform(sail, [0, 1], ["0%", "100%"]);

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    setActive(Math.min(STAGES.length - 1, Math.max(0, Math.floor(v * STAGES.length))));
  });

  const s = STAGES[active];
  const Art = ARTIFACTS[s.id];

  return (
    <section className="section pipe" id="how">
      <Flyby />
      <div className="wrap pipe-head-wrap">
        <Label n={1}>The voyage</Label>
        <Words className="h2 pipe-title" text="Seven ports of call, from a JSON file to a score you can *recompute.*" />
      </div>

      <div className="pipe-track" ref={track} style={{ height: `${STAGES.length * 80}vh` }}>
        <div className="pipe-sticky">
          <div className="wrap grid pipe-grid">
            <div className="pipe-emblem" aria-hidden>
              <AnimatePresence mode="popLayout">
                <motion.span
                  key={`n${s.id}`}
                  className="pipe-numeral"
                  initial={{ opacity: 0, y: 60 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -60 }}
                  transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                >
                  {NUMERALS[active]}
                </motion.span>
              </AnimatePresence>
              <AnimatePresence mode="popLayout">
                <motion.div
                  key={s.id}
                  className="pipe-emblem-img"
                  initial={{ opacity: 0, scale: 0.86, rotate: -6, filter: "blur(6px)" }}
                  animate={{ opacity: 1, scale: 1, rotate: 0, filter: "blur(0px)" }}
                  exit={{ opacity: 0, scale: 1.08, rotate: 6, filter: "blur(6px)" }}
                  transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                >
                  <Engraving name={EMBLEM[s.id]} />
                </motion.div>
              </AnimatePresence>
            </div>

            <div className="pipe-panel" aria-live="polite">
              <AnimatePresence mode="wait">
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, y: 22 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -14 }}
                  transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                >
                  <div className="pipe-head">
                    <span className="inscr pipe-port">
                      Port {active + 1} of {STAGES.length}
                    </span>
                    <Chip s={s.status} />
                  </div>
                  <h3 className="pipe-name">{s.title}</h3>
                  <p className="pipe-body">{s.body}</p>
                  <Art />
                  <p className="small pipe-note">{s.note}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          <div className="wrap pipe-route">
            <div className="route">
              <svg className="route-sea" viewBox="0 0 1200 24" preserveAspectRatio="none" aria-hidden>
                <path d="M0 12 Q 25 2 50 12 T 100 12 T 150 12 T 200 12 T 250 12 T 300 12 T 350 12 T 400 12 T 450 12 T 500 12 T 550 12 T 600 12 T 650 12 T 700 12 T 750 12 T 800 12 T 850 12 T 900 12 T 950 12 T 1000 12 T 1050 12 T 1100 12 T 1150 12 T 1200 12" />
              </svg>
              <ol className="route-ports">
                {STAGES.map((st, i) => (
                  <li key={st.id} className={i === active ? "on" : i < active ? "past" : ""}>
                    <i />
                    <span>{st.title}</span>
                  </li>
                ))}
              </ol>
              <motion.div className="route-ship" style={{ left: shipX }} aria-hidden>
                <div className="route-ship-in">
                  <Engraving name="ship" />
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </div>

      <ol className="wrap pipe-mobile">
        {STAGES.map((st, i) => {
          const A = ARTIFACTS[st.id];
          return (
            <li key={st.id}>
              <div className="pipe-m-emblem" aria-hidden>
                <span className="pipe-numeral">{NUMERALS[i]}</span>
                <Engraving name={EMBLEM[st.id]} />
              </div>
              <div className="pipe-head">
                <h3 className="pipe-name">{st.title}</h3>
                <Chip s={st.status} />
              </div>
              <p className="pipe-body">{st.body}</p>
              <A />
              <p className="small pipe-note">{st.note}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
