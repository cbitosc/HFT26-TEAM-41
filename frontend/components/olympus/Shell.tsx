"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";
import Meander from "./Meander";
import { gsap, prefersReducedMotion } from "@/lib/olympus/motion";

export const ROUTE_TITLES: Record<string, string> = {
  "/": "Olympus",
  "/ascend": "The Offering",
  "/trials": "Trials of Athena",
  "/labyrinth": "The Labyrinth",
  "/oracle": "The Oracle",
  "/verdict": "The Verdict",
};

const NIGHT_ROUTES = new Set(["/oracle"]);

type Nav = { navigate: (href: string) => void };
const NavContext = createContext<Nav>({ navigate: () => {} });
export const useNav = () => useContext(NavContext);

/**
 * Chrome shared by every themed page: grain and the curtain
 * transition between routes (cobalt panel rises, names the destination, then lifts).
 */
export default function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const curtain = useRef<HTMLDivElement>(null);
  const pending = useRef(false);
  const [title, setTitle] = useState("");

  const navigate = useCallback(
    (href: string) => {
      const path = href.split(/[?#]/)[0];
      if (path === pathname) return;
      if (prefersReducedMotion() || !curtain.current) {
        router.push(href);
        return;
      }
      setTitle(ROUTE_TITLES[path] ?? "");
      pending.current = true;
      gsap
        .timeline()
        // y: 0 drops the pixel offset GSAP reads from the CSS translateY(100%); yPercent drives it.
        .set(curtain.current, { y: 0, yPercent: 100, pointerEvents: "auto" })
        .to(curtain.current, { yPercent: 0, duration: 0.75, ease: "expo.inOut" })
        .fromTo(".curtain-title", { yPercent: 60, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.6, ease: "expo.out" }, "-=0.3")
        .add(() => router.push(href));
    },
    [pathname, router],
  );

  useEffect(() => {
    window.scrollTo(0, 0);
    if (!pending.current || !curtain.current) return;
    pending.current = false;
    gsap
      .timeline({ delay: 0.25 })
      .to(".curtain-title", { yPercent: -40, opacity: 0, duration: 0.4, ease: "power2.in" })
      .to(curtain.current, { yPercent: -100, duration: 0.85, ease: "expo.inOut" }, "-=0.1")
      .set(curtain.current, { pointerEvents: "none" });
  }, [pathname]);

  const night = NIGHT_ROUTES.has(pathname);

  return (
    <NavContext.Provider value={{ navigate }}>
      <div className={`oly ${night ? "oly-night" : ""}`}>
        {children}
        <div className="oly-grain" aria-hidden="true" />
        <div ref={curtain} className="curtain" aria-hidden="true">
          <div className="curtain-key" style={{ top: 28 }}>
            <Meander height={16} />
          </div>
          <p className="curtain-title">{title}</p>
          <div className="curtain-key" style={{ bottom: 28 }}>
            <Meander height={16} />
          </div>
        </div>
      </div>
    </NavContext.Provider>
  );
}

/** A link that plays the curtain transition. Modifier-clicks open normally. */
export function TLink({ href, onClick, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const { navigate } = useNav();
  return (
    <Link
      href={href}
      {...rest}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </Link>
  );
}
