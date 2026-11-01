"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "motion/react";
import { GREEK, NUMERALS, type GreekName } from "@/lib/greek";

const EASE = [0.22, 1, 0.36, 1] as const;

/**
 * One engraving, drawn from two alpha masks so the theme colours it: a silhouette in
 * the page colour (layered figures hide what's behind them) under the line work in
 * engraving ink. `ink`: the line work alone, in `currentColor`, for the night
 * sections. Masks load when the engraving comes within 1200 px of the viewport.
 */
export function Engraving({
  name,
  ink = false,
  className,
  alt = "",
  eager = false,
  style,
}: {
  name: GreekName;
  ink?: boolean;
  className?: string;
  alt?: string;
  eager?: boolean;
  style?: React.CSSProperties;
}) {
  const [w, h] = GREEK[name];
  const ref = useRef<HTMLSpanElement>(null);
  const [near, setNear] = useState(eager);

  useEffect(() => {
    if (near || !ref.current) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setNear(true);
          io.disconnect();
        }
      },
      { rootMargin: "1200px" },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [near]);

  const mask = (kind: "ink" | "sil"): React.CSSProperties | undefined => {
    if (!near) return undefined;
    const url = `url(/greek/${name}-${kind}.webp)`;
    return { WebkitMaskImage: url, maskImage: url };
  };

  return (
    <span
      ref={ref}
      className={`engr ${ink ? "engr-ink" : ""} ${className ?? ""}`}
      role={alt ? "img" : undefined}
      aria-label={alt || undefined}
      aria-hidden={alt ? undefined : true}
      style={{ aspectRatio: `${w} / ${h}`, ...style }}
    >
      {!ink && <span className="engr-sil" style={mask("sil")} />}
      <span className="engr-lines" style={mask("ink")} />
    </span>
  );
}

/** Moves its child vertically while it crosses the viewport: `speed` px per 100 px. */
export function Parallax({
  children,
  speed = 12,
  className,
}: {
  children: React.ReactNode;
  speed?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [`${speed}%`, `${-speed}%`]);
  return (
    <motion.div ref={ref} className={className} style={{ y: reduce ? 0 : y }}>
      {children}
    </motion.div>
  );
}

/** A heading whose words rise out of a mask, staggered, the first time it's seen. */
export function Words({
  text,
  as = "h2",
  className,
  delay = 0,
}: {
  text: string;
  as?: "h1" | "h2" | "h3" | "p";
  className?: string;
  delay?: number;
}) {
  const M = motion[as];
  // *word* renders as an italic accent.
  const words = text.split(" ");
  return (
    <M
      className={className}
      initial="hidden"
      whileInView="shown"
      viewport={{ once: true, amount: 0.4 }}
      transition={{ staggerChildren: 0.045, delayChildren: delay }}
      aria-label={text.replace(/\*/g, "")}
    >
      {words.map((w, i) => {
        const em = w.startsWith("*");
        const clean = w.replace(/\*/g, "");
        return (
          <Fragment key={i}>
            <span className="word" aria-hidden>
              <motion.span
                className={em ? "word-in em" : "word-in"}
                variants={{
                  hidden: { y: "110%", rotate: 4 },
                  shown: { y: "0%", rotate: 0, transition: { duration: 0.9, ease: EASE } },
                }}
              >
                {clean}
              </motion.span>
            </span>
            {i < words.length - 1 ? " " : ""}
          </Fragment>
        );
      })}
    </M>
  );
}

/** Section label: a Greek numeral, a rule, a name. */
export function Label({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <p className="label">
      <span className="label-n">{NUMERALS[n]}΄</span>
      <span className="label-rule" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

/** Pulls its child toward the pointer while hovered. */
export function Magnetic({ children, strength = 0.3 }: { children: React.ReactNode; strength?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const x = useSpring(0, { stiffness: 220, damping: 16, mass: 0.4 });
  const y = useSpring(0, { stiffness: 220, damping: 16, mass: 0.4 });
  return (
    <motion.span
      ref={ref}
      className="magnetic"
      style={{ x, y }}
      onPointerMove={(e) => {
        if (e.pointerType !== "mouse") return;
        const r = ref.current!.getBoundingClientRect();
        x.set((e.clientX - r.left - r.width / 2) * strength);
        y.set((e.clientY - r.top - r.height / 2) * strength);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.span>
  );
}

/** Tilts its child in 3D toward the pointer, with a moving sheen. */
export function Tilt({
  children,
  className,
  max = 8,
}: {
  children: React.ReactNode;
  className?: string;
  max?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const sx = useSpring(px, { stiffness: 160, damping: 18 });
  const sy = useSpring(py, { stiffness: 160, damping: 18 });
  const rotateY = useTransform(sx, [0, 1], [-max, max]);
  const rotateX = useTransform(sy, [0, 1], [max, -max]);
  const sheen = useTransform(
    [sx, sy] as MotionValue<number>[],
    ([a, b]: number[]) =>
      `radial-gradient(circle at ${a * 100}% ${b * 100}%, rgba(255,250,235,.55), rgba(255,250,235,0) 55%)`,
  );
  return (
    <motion.div
      ref={ref}
      className={`tilt ${className ?? ""}`}
      style={{ rotateX, rotateY, transformPerspective: 900 }}
      onPointerMove={(e) => {
        if (e.pointerType !== "mouse") return;
        const r = ref.current!.getBoundingClientRect();
        px.set((e.clientX - r.left) / r.width);
        py.set((e.clientY - r.top) / r.height);
      }}
      onPointerLeave={() => {
        px.set(0.5);
        py.set(0.5);
      }}
    >
      {children}
      <motion.span className="tilt-sheen" style={{ backgroundImage: sheen }} aria-hidden />
    </motion.div>
  );
}

/** An eight-pointed engraver's star, as on the sheets. */
export function Star({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`star ${className ?? ""}`} aria-hidden>
      <path d="M12 0 13.4 10.6 24 12 13.4 13.4 12 24 10.6 13.4 0 12 10.6 10.6Z" fill="currentColor" />
      <path d="M12 6.5 12.9 11.1 17.5 12 12.9 12.9 12 17.5 11.1 12.9 6.5 12 11.1 11.1Z" fill="currentColor" transform="rotate(45 12 12)" />
    </svg>
  );
}

/** A Greek key band, drawn as a repeating SVG pattern so it's crisp at any width. */
export function Meander({ className }: { className?: string }) {
  return <div className={`meander ${className ?? ""}`} aria-hidden />;
}
