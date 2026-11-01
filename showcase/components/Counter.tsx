"use client";

import { useEffect, useRef, useState } from "react";
import { animate, useInView, useReducedMotion } from "motion/react";

/** Counts up to `to` once, the first time it's on screen. */
export default function Counter({ to, decimals = 0, prefix = "", suffix = "" }: {
  to: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.6 });
  const reduce = useReducedMotion();
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!seen) return;
    if (reduce) {
      setValue(to);
      return;
    }
    const controls = animate(0, to, { duration: 1.4, ease: [0.22, 1, 0.36, 1], onUpdate: setValue });
    return () => controls.stop();
  }, [seen, reduce, to]);

  // Reserve the final width so counting never shifts the layout.
  const final = `${prefix}${to.toFixed(decimals)}${suffix}`;
  return (
    <span ref={ref} style={{ display: "inline-grid", fontVariantNumeric: "tabular-nums" }}>
      <span aria-hidden style={{ gridArea: "1/1", visibility: "hidden" }}>{final}</span>
      <span style={{ gridArea: "1/1" }}>{`${prefix}${value.toFixed(decimals)}${suffix}`}</span>
    </span>
  );
}
