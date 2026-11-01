"use client";
// Small interactive building blocks: smooth scroll, magnetic hover, the rolling-label
// button, line-by-line text reveals and the scroll-in fade.
import Lenis from "lenis";
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { IconArrow } from "./Icons";
import { TLink } from "./Shell";
import { gsap, prefersReducedMotion, ScrollTrigger, SplitText, useGsap } from "@/lib/olympus/motion";

/** Lenis smooth scrolling driven by GSAP's ticker, so ScrollTrigger stays in sync. */
export function SmoothScroll() {
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const lenis = new Lenis({ lerp: 0.085, wheelMultiplier: 0.95 });
    lenis.on("scroll", ScrollTrigger.update);
    const tick = (t: number) => lenis.raf(t * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => {
      gsap.ticker.remove(tick);
      lenis.destroy();
    };
  }, []);
  return null;
}

/** Pulls its child toward the pointer while hovered. */
export function Magnetic({ children, strength = 0.35, className = "" }: { children: ReactNode; strength?: number; className?: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = el.current;
    if (!node || !window.matchMedia("(pointer: fine)").matches || prefersReducedMotion()) return;
    const x = gsap.quickTo(node, "x", { duration: 0.8, ease: "elastic.out(1, 0.4)" });
    const y = gsap.quickTo(node, "y", { duration: 0.8, ease: "elastic.out(1, 0.4)" });
    const move = (e: PointerEvent) => {
      const r = node.getBoundingClientRect();
      x((e.clientX - r.left - r.width / 2) * strength);
      y((e.clientY - r.top - r.height / 2) * strength);
    };
    const leave = () => {
      x(0);
      y(0);
    };
    node.addEventListener("pointermove", move);
    node.addEventListener("pointerleave", leave);
    return () => {
      node.removeEventListener("pointermove", move);
      node.removeEventListener("pointerleave", leave);
    };
  }, [strength]);
  return (
    <div ref={el} className={`inline-block ${className}`}>
      {children}
    </div>
  );
}

type BtnProps = { children: string; variant?: "ink" | "ghost" | "moon"; size?: "md" | "sm"; icon?: ReactNode; magnetic?: boolean };

function BtnInner({ children, icon }: { children: string; icon?: ReactNode }) {
  return (
    <>
      <span className="btn-label">
        <span>{children}</span>
        <span aria-hidden="true">{children}</span>
      </span>
      <span className="btn-icon">{icon ?? <IconArrow size={14} />}</span>
    </>
  );
}

function btnClass(variant: BtnProps["variant"], size: BtnProps["size"], extra = "") {
  return `btn ${variant === "ghost" ? "btn-ghost" : variant === "moon" ? "btn-moon" : ""} ${size === "sm" ? "btn-sm" : ""} ${extra}`;
}

/** Pill button whose label rolls on hover; renders a transition link when given href. */
export function Btn({
  children,
  variant = "ink",
  size = "md",
  icon,
  magnetic = true,
  href,
  className,
  ...rest
}: BtnProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: string }) {
  const inner = href ? (
    <TLink href={href} className={btnClass(variant, size, className)}>
      <BtnInner icon={icon}>{children}</BtnInner>
    </TLink>
  ) : (
    <button className={btnClass(variant, size, className)} {...rest}>
      <BtnInner icon={icon}>{children}</BtnInner>
    </button>
  );
  return magnetic ? <Magnetic strength={0.25}>{inner}</Magnetic> : inner;
}

/** Splits text into masked lines that rise into place when scrolled into view (or at once). */
export function RevealText({
  children,
  as: Tag = "div",
  className = "",
  delay = 0,
  immediate = false,
  stagger = 0.09,
}: {
  children: ReactNode;
  as?: "div" | "h1" | "h2" | "h3" | "p";
  className?: string;
  delay?: number;
  immediate?: boolean;
  stagger?: number;
}) {
  const el = useRef<HTMLElement>(null);
  useGsap(el, (reduced) => {
    if (reduced || !el.current) return;
    const split = SplitText.create(el.current, { type: "lines", mask: "lines", linesClass: "split-line-inner" });
    gsap.from(split.lines, {
      yPercent: 115,
      rotate: 2.5,
      duration: 1.25,
      stagger,
      delay,
      ease: "expo.out",
      scrollTrigger: immediate ? undefined : { trigger: el.current, start: "top 88%" },
    });
    return () => split.revert();
  });
  return (
    // @ts-expect-error: polymorphic ref across the allowed tags
    <Tag ref={el} className={className}>
      {children}
    </Tag>
  );
}

/** Fades and lifts its children in when they scroll into view. */
export function FadeIn({ children, className = "", delay = 0, y = 40 }: { children: ReactNode; className?: string; delay?: number; y?: number }) {
  const el = useRef<HTMLDivElement>(null);
  useGsap(el, (reduced) => {
    if (reduced) return;
    gsap.from(el.current, { y, opacity: 0, duration: 1.2, delay, ease: "expo.out", scrollTrigger: { trigger: el.current, start: "top 90%" } });
  });
  return (
    <div ref={el} className={className}>
      {children}
    </div>
  );
}
