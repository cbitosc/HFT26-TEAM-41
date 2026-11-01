// Line icons drawn for the theme (1.5px strokes, 24px grid, currentColor).
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...rest }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      {children}
    </svg>
  );
}

export const IconArrow = (p: P) => (
  <Svg {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Svg>
);
export const IconArrowDown = (p: P) => (
  <Svg {...p}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </Svg>
);
/** Hermes' wing: the AI hint. */
export const IconHermesWing = (p: P) => (
  <Svg {...p}>
    <path d="M3.5 18.5C8 17.6 14.6 12.8 20.5 4.5 14.8 6.4 8.6 9.6 3.5 18.5Z" />
    <path d="M3.5 18.5c4.8.4 10.3-1.6 14.8-6.3" />
    <path d="M3.5 18.5c3.6 1.6 8 1.5 11.9-.6" />
    <path d="M9.6 12.6l2.3 1.3M12.9 9.6l2.4 1.2" />
  </Svg>
);
/** A scroll condensing into a star: the AI summary. */
export const IconSummarize = (p: P) => (
  <Svg {...p}>
    <path d="M4 6.5h9M4 11h7M4 15.5h5M4 20h3" />
    <path d="M17.5 7.5l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z" />
  </Svg>
);
export const IconSparkle = (p: P) => (
  <Svg {...p}>
    <path d="M12 3l1.8 5.6L19.5 10l-5.7 1.6L12 17.5l-1.8-5.9L4.5 10l5.7-1.4z" />
    <path d="M19 16.5l.6 1.8 1.9.7-1.9.6-.6 1.9-.6-1.9-1.9-.6 1.9-.7z" />
  </Svg>
);
/** Ariadne's ball of thread. */
export const IconThread = (p: P) => (
  <Svg {...p}>
    <circle cx="10" cy="10" r="6.5" />
    <path d="M5.3 7.5c3 .3 6.8 2.4 8.9 6.1M4.4 11.6c2.6-.4 6.3.4 9.3 3M8 3.8c1.4 2.3 2.2 6.3 1.4 9.8" />
    <path d="M14.6 14.6c1.8 1.8 3 2.3 4.1 2 1.3-.4 1.7 1.4 1 2.8" />
  </Svg>
);
export const IconUpload = (p: P) => (
  <Svg {...p}>
    <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
  </Svg>
);
export const IconCheck = (p: P) => (
  <Svg {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Svg>
);
export const IconX = (p: P) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Svg>
);
export const IconPlay = (p: P) => (
  <Svg {...p}>
    <path d="M7 5l12 7-12 7z" />
  </Svg>
);
export const IconSend = (p: P) => (
  <Svg {...p}>
    <path d="M4 12l16-8-6 16-2.5-6.5z" />
  </Svg>
);
export const IconMic = (p: P) => (
  <Svg {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
  </Svg>
);
export const IconMicOff = (p: P) => (
  <Svg {...p}>
    <path d="M15 9.5V6a3 3 0 0 0-5.8-1M9 9v2a3 3 0 0 0 4.6 2.5M5.5 11a6.5 6.5 0 0 0 10.4 5.2M18.5 11c0 .7-.1 1.3-.3 1.9M12 17.5V21M4 4l16 16" />
  </Svg>
);
export const IconPause = (p: P) => (
  <Svg {...p}>
    <path d="M8 5v14M16 5v14" />
  </Svg>
);
export const IconStop = (p: P) => (
  <Svg {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </Svg>
);
export const IconSkip = (p: P) => (
  <Svg {...p}>
    <path d="M5 5l10 7-10 7zM19 5v14" />
  </Svg>
);
export const IconFile = (p: P) => (
  <Svg {...p}>
    <path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z" />
    <path d="M14 3v4h4" />
  </Svg>
);
export const IconFolder = (p: P) => (
  <Svg {...p}>
    <path d="M3.5 6.5a1 1 0 0 1 1-1h4.3l2 2h8.7a1 1 0 0 1 1 1v9.5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1z" />
  </Svg>
);
export const IconLock = (p: P) => (
  <Svg {...p}>
    <rect x="5" y="11" width="14" height="9.5" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </Svg>
);
export const IconBug = (p: P) => (
  <Svg {...p}>
    <rect x="7.5" y="8" width="9" height="12" rx="4.5" />
    <path d="M12 8v12M9 5.5l1.5 2.5M15 5.5L13.5 8M4 11h3.5M16.5 11H20M4 17h3.5M16.5 17H20" />
  </Svg>
);
export const IconGauge = (p: P) => (
  <Svg {...p}>
    <path d="M4.5 17a8.5 8.5 0 1 1 15 0" />
    <path d="M12 13.5l4-4.5" />
    <circle cx="12" cy="14" r="1.2" />
  </Svg>
);
export const IconEye = (p: P) => (
  <Svg {...p}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
    <circle cx="12" cy="12" r="3" />
  </Svg>
);
export const IconClock = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Svg>
);
export const IconStar = (p: P) => (
  <Svg {...p} strokeWidth={1.2}>
    <path d="M12 2.5l1.6 8 7.9 1.5-7.9 1.6L12 21.5l-1.6-7.9L2.5 12l7.9-1.5z" />
  </Svg>
);
export const IconDownload = (p: P) => (
  <Svg {...p}>
    <path d="M12 4v12M7 11l5 5 5-5M4 20h16" />
  </Svg>
);
export const IconLink = (p: P) => (
  <Svg {...p}>
    <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
  </Svg>
);
export const IconBranch = (p: P) => (
  <Svg {...p}>
    <circle cx="6" cy="5.5" r="2" />
    <circle cx="6" cy="18.5" r="2" />
    <circle cx="18" cy="7.5" r="2" />
    <path d="M6 7.5v9M18 9.5c0 4-6 3-11 7" />
  </Svg>
);

/** The small four-point star used as a text separator. */
export function Star({ className = "" }: { className?: string }) {
  return (
    <svg className={className} width="0.55em" height="0.55em" viewBox="0 0 24 24" aria-hidden="true" style={{ display: "inline-block" }}>
      <path d="M12 0l2.2 9.8L24 12l-9.8 2.2L12 24l-2.2-9.8L0 12l9.8-2.2z" fill="currentColor" />
    </svg>
  );
}
