"use client";

import { useState } from "react";
import { motion, useMotionValueEvent, useScroll, useSpring } from "motion/react";
import Link from "next/link";
import { NAME, PRACTICE_URL } from "@/lib/site";
import { Star } from "./fx";
import ThemeToggle from "./ThemeToggle";

const LINKS = [
  ["#try", "Try it"],
  ["#how", "Voyage"],
  ["#trail", "Thread"],
  ["#trust", "Aegis"],
  ["#progress", "Ascent"],
  ["#stack", "Temple"],
];

// Hides while the reader scrolls down, comes back on the way up; gains a paper
// backing once past the hero.
export default function Header() {
  const { scrollY, scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 200, damping: 40, mass: 0.3 });
  const [hidden, setHidden] = useState(false);
  const [solid, setSolid] = useState(false);

  useMotionValueEvent(scrollY, "change", (y) => {
    const prev = scrollY.getPrevious() ?? 0;
    setHidden(y > prev && y > 240);
    setSolid(y > 80);
  });

  return (
    <motion.header
      className={`hdr ${solid ? "solid" : ""}`}
      animate={{ y: hidden ? "-100%" : "0%" }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="wrap hdr-in">
        <a href="#top" className="hdr-mark">
          <Star />
          {NAME}
        </a>
        <div className="hdr-right">
          <nav aria-label="Sections">
            {LINKS.map(([href, label]) => (
              <a key={href} href={href}>
                <span data-text={label}>{label}</span>
              </a>
            ))}
          </nav>
          <a href={PRACTICE_URL} className="hdr-cc">
            Practice
          </a>
          <ThemeToggle />
          <Link href="/comprehension" className="hdr-cc">
            Code reading
          </Link>
          <Link href="/interview" className="hdr-ai">
            <span className="hdr-blob" aria-hidden />
            AI interview
          </Link>
        </div>
      </div>
      <motion.div className="hdr-bar" style={{ scaleX }} />
    </motion.header>
  );
}
