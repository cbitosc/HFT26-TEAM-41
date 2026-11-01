// GSAP setup shared by the themed pages. Plugins register once, in the browser.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useEffect, useLayoutEffect, type DependencyList, type RefObject } from "react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, SplitText);
}

export { gsap, ScrollTrigger, SplitText };

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Runs `setup` inside a gsap.context scoped to `scope`; everything it creates is reverted on cleanup. */
export function useGsap(scope: RefObject<HTMLElement | null>, setup: (reduced: boolean) => void | (() => void), deps: DependencyList = []) {
  useIsoLayoutEffect(() => {
    if (!scope.current) return;
    let cleanup: void | (() => void);
    const ctx = gsap.context(() => {
      cleanup = setup(prefersReducedMotion());
    }, scope);
    return () => {
      cleanup?.();
      ctx.revert();
    };
  }, deps);
}

export const EASE = {
  out: "expo.out",
  inOut: "expo.inOut",
  soft: "power3.out",
};
