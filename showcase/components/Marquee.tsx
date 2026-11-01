"use client";

import { useRef } from "react";
import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
} from "motion/react";
import { Star } from "./fx";

// An inscribed band that drifts on its own and speeds up (or reverses) with the
// reader's scroll velocity.
export default function Marquee({ items, speed = 40 }: { items: string[]; speed?: number }) {
  const reduce = useReducedMotion();
  const base = useMotionValue(0);
  const { scrollY } = useScroll();
  const vel = useSpring(useVelocity(scrollY), { damping: 50, stiffness: 300 });
  const boost = useTransform(vel, [-2000, 0, 2000], [-4, 0, 4], { clamp: false });
  const dir = useRef(1);
  const x = useTransform(base, (v) => `${((v % 50) + 50) % 50 - 50}%`);

  useAnimationFrame((_, delta) => {
    if (reduce) return;
    const b = boost.get();
    if (b < -0.2) dir.current = -1;
    else if (b > 0.2) dir.current = 1;
    base.set(base.get() + dir.current * (speed / 1000) * (delta / 16) * 0.08 * (1 + Math.abs(b)));
  });

  const row = (
    <span className="mq-row">
      {items.map((t) => (
        <span key={t} className="mq-item">
          {t}
          <Star />
        </span>
      ))}
    </span>
  );

  return (
    <div className="mq dark" aria-hidden>
      <motion.div className="mq-track" style={{ x }}>
        {row}
        {row}
        {row}
        {row}
      </motion.div>
    </div>
  );
}
