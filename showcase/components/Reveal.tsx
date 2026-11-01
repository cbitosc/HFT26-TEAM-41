"use client";

import { motion, type Variants } from "motion/react";

const parent: Variants = {
  hidden: {},
  shown: { transition: { staggerChildren: 0.06 } },
};

export const rise: Variants = {
  hidden: { opacity: 0, y: 24 },
  shown: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
};

type Props = {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "ul" | "ol" | "section";
  amount?: number;
};

/** Staggers its direct <Item> children in once, when scrolled into view. */
export function Reveal({ children, className, as = "div", amount = 0.25 }: Props) {
  const M = motion[as];
  return (
    <M className={className} variants={parent} initial="hidden" whileInView="shown" viewport={{ once: true, amount }}>
      {children}
    </M>
  );
}

export function Item({
  children,
  className,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "li" | "p" | "h2" | "h3" | "span";
}) {
  const M = motion[as];
  return (
    <M className={className} variants={rise}>
      {children}
    </M>
  );
}
