"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

// Day (parchment) or night (lapis). The choice is saved per browser; until one is
// made the page follows the system setting, including when it changes.
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const read = () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    setTheme(read());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onSystem = () => {
      let saved: string | null = null;
      try {
        saved = localStorage.getItem("theme");
      } catch {}
      if (saved) return;
      document.documentElement.dataset.theme = mq.matches ? "dark" : "light";
      setTheme(read());
    };
    mq.addEventListener("change", onSystem);
    return () => mq.removeEventListener("change", onSystem);
  }, []);

  const flip = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {}
    setTheme(next);
  };

  const dark = theme === "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={flip}
      aria-label={dark ? "Switch to the light theme" : "Switch to the dark theme"}
      title={dark ? "Day" : "Night"}
      data-dark={dark}
    >
      <svg viewBox="0 0 24 24" aria-hidden>
        <g className="tt-sun">
          <circle cx="12" cy="12" r="4.2" />
          {Array.from({ length: 8 }, (_, i) => {
            const a = (i * Math.PI) / 4;
            return (
              <line
                key={i}
                x1={+(12 + Math.cos(a) * 7).toFixed(2)}
                y1={+(12 + Math.sin(a) * 7).toFixed(2)}
                x2={+(12 + Math.cos(a) * 9.5).toFixed(2)}
                y2={+(12 + Math.sin(a) * 9.5).toFixed(2)}
              />
            );
          })}
        </g>
        <path className="tt-moon" d="M15.5 3.5a8.5 8.5 0 1 0 5 15.2A7 7 0 0 1 15.5 3.5Z" />
      </svg>
    </button>
  );
}
