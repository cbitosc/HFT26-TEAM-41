"use client";

import { useMemo, useRef } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "motion/react";
import { AGENT, EVENT, NAME } from "@/lib/site";
import { Engraving, Magnetic, Star } from "./fx";
import { useIntroDone } from "./Intro";

const EASE = [0.22, 1, 0.36, 1] as const;

// The hero is a stage in depth: an astrolabe (the halo), Athena, the name in front of
// her, and loose stars. The pointer shifts each layer by a different amount; scrolling
// lifts Athena out of the letters while the name sinks.

function rng(seed: number) {
  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

const RING_TEXT =
  "The candidate’s own work ✦ in their own stack ✦ checked before anyone sees it ✦ graded by tests alone ✦ re-graded to the byte ✦ ";

function Astrolabe() {
  const { ticks, stars, lines } = useMemo(() => {
    const r = rng(41);
    const ticks = Array.from({ length: 360 }, (_, i) => {
      const a = (i * Math.PI) / 180;
      const len = i % 30 === 0 ? 26 : i % 5 === 0 ? 14 : 7;
      // Rounded so the server and the browser print identical attributes.
      return [470, 470, 470 - len, 470 - len].map((d, k) => +((k % 2 ? Math.sin(a) : Math.cos(a)) * d).toFixed(2));
    });
    const stars = Array.from({ length: 90 }, () => {
      const a = r() * Math.PI * 2;
      const d = 60 + Math.sqrt(r()) * 330;
      return [+(Math.cos(a) * d).toFixed(1), +(Math.sin(a) * d).toFixed(1), +(0.7 + r() * 1.9).toFixed(2)];
    });
    // Constellations: short chains through nearby stars.
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
    <svg viewBox="-500 -500 1000 1000" className="astro" aria-hidden>
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
            <line key={i} x1={+(Math.cos(a) * 210).toFixed(2)} y1={+(Math.sin(a) * 210).toFixed(2)} x2={+(Math.cos(a) * 404).toFixed(2)} y2={+(Math.sin(a) * 404).toFixed(2)} className="a-line a-faint" />
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

function useLayer(mx: MotionValue<number>, my: MotionValue<number>, depth: number) {
  return {
    x: useTransform(mx, (v) => v * depth),
    y: useTransform(my, (v) => v * depth),
  };
}

export default function Hero() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const ready = useIntroDone();
  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const mx = useSpring(px, { stiffness: 60, damping: 18, mass: 0.6 });
  const my = useSpring(py, { stiffness: 60, damping: 18, mass: 0.6 });

  const far = useLayer(mx, my, -14);
  const mid = useLayer(mx, my, 10);
  const near = useLayer(mx, my, 26);
  const front = useLayer(mx, my, 40);

  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const athenaY = useTransform(scrollYProgress, [0, 1], ["0%", "-18%"]);
  const titleY = useTransform(scrollYProgress, [0, 1], ["0%", "38%"]);
  const fade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);
  const astroScale = useTransform(scrollYProgress, [0, 1], [1, 1.25]);
  const astroRot = useTransform(scrollYProgress, [0, 1], [0, 40]);

  const show = ready || !!reduce;

  return (
    <section
      className="hero"
      id="top"
      ref={ref}
      onPointerMove={(e) => {
        if (e.pointerType !== "mouse" || reduce) return;
        px.set(e.clientX / window.innerWidth - 0.5);
        py.set(e.clientY / window.innerHeight - 0.5);
      }}
    >
      <div className="hero-stage">
        <motion.div className="hero-astro" style={{ ...far, scale: astroScale, rotate: astroRot }}>
          <motion.div
            initial={{ opacity: 0, scale: 0.85, rotate: -30 }}
            animate={show ? { opacity: 1, scale: 1, rotate: 0 } : {}}
            transition={{ duration: 2.2, ease: EASE }}
          >
            <Astrolabe />
          </motion.div>
        </motion.div>

        <motion.div className="hero-athena" style={{ ...mid, y: athenaY }}>
          <motion.div
            initial={{ opacity: 0, y: 80 }}
            animate={show ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 1.6, delay: 0.15, ease: EASE }}
          >
            <motion.div style={near}>
              <Engraving name="athena" eager alt="Athena with spear and shield, a blue engraving" />
            </motion.div>
          </motion.div>
        </motion.div>

        <motion.div className="hero-stars" style={front} aria-hidden>
          {[
            [12, 28, 18],
            [84, 22, 12],
            [76, 58, 20],
            [22, 62, 10],
            [64, 14, 9],
            [34, 18, 8],
          ].map(([l, t, s], i) => (
            <motion.span
              key={i}
              style={{ left: `${l}%`, top: `${t}%`, width: s, height: s }}
              initial={{ opacity: 0, scale: 0 }}
              animate={show ? { opacity: 1, scale: 1 } : {}}
              transition={{ duration: 0.8, delay: 0.9 + i * 0.08, ease: EASE }}
            >
              <Star />
            </motion.span>
          ))}
        </motion.div>

        <motion.h1 className="hero-name display" style={{ y: titleY }} aria-label={NAME}>
          <motion.span className="hero-name-in" style={far}>
            {NAME.split("").map((ch, i) => (
              <span key={i} className="hero-ch" aria-hidden>
                <motion.span
                  initial={{ y: "105%" }}
                  animate={show ? { y: "0%" } : {}}
                  transition={{ duration: 1.3, delay: 0.25 + i * 0.07, ease: EASE }}
                >
                  {ch}
                </motion.span>
              </span>
            ))}
          </motion.span>
        </motion.h1>
      </div>

      <motion.div className="wrap hero-top" style={{ opacity: fade }}>
        <motion.div
          className="hero-copy"
          initial={{ opacity: 0, y: 24 }}
          animate={show ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 1, delay: 0.7, ease: EASE }}
        >
          <p className="hero-promise">
            A coding assessment built from the candidate&apos;s <em>own</em> portfolio, and graded only by tests.
          </p>
          <p className="hero-sub">
            Upload a portfolio. Get a 60-minute task in the candidate&apos;s stack and domain, validated in a sandbox
            before anyone sees it. The score comes from test results and fixed formulas, and you can recompute it.
          </p>
          <div className="hero-cta">
            <Magnetic>
              <a href="#how" className="btn btn-solid">
                How it works
              </a>
            </Magnetic>
            <Magnetic>
              <a href="/interview" className="btn">
                Try the AI interview
              </a>
            </Magnetic>
          </div>
        </motion.div>

        <motion.aside
          className="hero-plate"
          initial={{ opacity: 0, y: 24 }}
          animate={show ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 1, delay: 0.85, ease: EASE }}
        >
          <p className="inscr">Plate I · Athena</p>
          <p className="small">
            In the Eumenides, Athena ends a blood feud by founding the first court: evidence is heard, votes are
            counted, and nobody&apos;s anger decides. We built the same thing for code, under Apollo, god of truth,
            and {AGENT} is the voice that interviews the candidate.
          </p>
          <p className="inscr hero-event">
            {EVENT} · Team XLI
          </p>
        </motion.aside>
      </motion.div>

      <motion.a href="#problem" className="hero-scroll" style={{ opacity: fade }} aria-label="Scroll to the next section">
        <span className="inscr">Scroll</span>
        <i aria-hidden />
      </motion.a>
    </section>
  );
}
