"use client";

import { useEffect, useState } from "react";
import { animate, motion, useReducedMotion } from "motion/react";
import { NAME } from "@/lib/site";
import { Engraving } from "./fx";

// A short opening plate: a laurel, a count to 100 (the demo's score), then the curtain
// lifts and the hero starts. Once per tab; reduced motion skips it.
let done = false;
const listeners = new Set<() => void>();

function finish() {
  done = true;
  listeners.forEach((f) => f());
}

/** True once the opening plate has lifted. */
export function useIntroDone() {
  const [d, setD] = useState(done);
  useEffect(() => {
    if (done) return setD(true);
    const f = () => setD(true);
    listeners.add(f);
    return () => {
      listeners.delete(f);
    };
  }, []);
  return d;
}

export default function Intro() {
  const reduce = useReducedMotion();
  const [n, setN] = useState(0);
  const [lift, setLift] = useState(false);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    let seen = false;
    try {
      seen = sessionStorage.getItem("intro") === "1";
      sessionStorage.setItem("intro", "1");
    } catch {}
    if (reduce || seen) {
      setGone(true);
      finish();
      return;
    }
    document.documentElement.classList.add("intro-lock");
    const c = animate(0, 100, { duration: 1.5, ease: [0.65, 0, 0.35, 1], onUpdate: (v) => setN(Math.round(v)) });
    const t1 = setTimeout(() => {
      setLift(true);
      finish();
    }, 1750);
    const t2 = setTimeout(() => {
      setGone(true);
      document.documentElement.classList.remove("intro-lock");
    }, 2700);
    return () => {
      c.stop();
      clearTimeout(t1);
      clearTimeout(t2);
      document.documentElement.classList.remove("intro-lock");
    };
  }, [reduce]);

  if (gone) return null;
  return (
    <motion.div
      className="intro"
      aria-hidden
      initial={{ clipPath: "inset(0 0 0% 0)" }}
      animate={lift ? { clipPath: "inset(0 0 100% 0)" } : {}}
      transition={{ duration: 0.95, ease: [0.76, 0, 0.24, 1] }}
    >
      <motion.div
        className="intro-plate"
        animate={lift ? { y: -60, opacity: 0 } : {}}
        transition={{ duration: 0.6, ease: [0.76, 0, 0.24, 1] }}
      >
        <motion.div
          className="intro-wreath"
          initial={{ clipPath: "inset(100% 0 0 0)", rotate: -8 }}
          animate={{ clipPath: "inset(0% 0 0 0)", rotate: 0 }}
          transition={{ duration: 1.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <Engraving name="wreath-bow" eager />
          <span className="intro-n">{n}</span>
        </motion.div>
        <p className="intro-name inscr">{NAME}</p>
      </motion.div>
    </motion.div>
  );
}
