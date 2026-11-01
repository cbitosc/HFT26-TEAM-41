// The candidate's journey through the five rounds, kept in localStorage so a reload or a
// new tab resumes where they left off. Read it with useJourney(); write with updateJourney().
import { useSyncExternalStore } from "react";
import type { Profile } from "@/lib/types";

export type Candidate = {
  name: string;
  email: string;
  resumeName: string | null;
  github: string;
  leetcode: string;
  codeforces: string;
  portfolio: string;
  stack: string[];
};

export type TaskOutcome = {
  id: string;
  title: string;
  kind: "domain" | "dsa";
  visible: [passed: number, total: number];
  hidden: [passed: number, total: number];
  runs: number;
  seconds: number;
};

export type TrialsResult = {
  tasks: TaskOutcome[];
  hintLevels: number[];
  quiz: { correct: number; total: number };
  completedAt: string;
};

export type LabyrinthResult = {
  issuesResolved: number;
  issuesTotal: number;
  findings: number;
  perfIdeas: number;
  filesTouched: number;
  questionsAsked: number;
  completedAt: string;
};

export type OracleResult = {
  answered: number;
  total: number;
  seconds: number;
  transcript: { q: string; a: string }[];
  completedAt: string;
};

export type Journey = {
  candidate: Candidate | null;
  profile: Profile | null;
  assessmentId: string | null;
  offline: boolean; // the API was unreachable, so the demo profile is used
  trials: TrialsResult | null;
  labyrinth: LabyrinthResult | null;
  oracle: OracleResult | null;
  reportAt: string | null;
};

const KEY = "arete.journey.v1";
export const EMPTY_JOURNEY: Journey = {
  candidate: null,
  profile: null,
  assessmentId: null,
  offline: false,
  trials: null,
  labyrinth: null,
  oracle: null,
  reportAt: null,
};

const listeners = new Set<() => void>();
let memRaw: string | null = null; // used when storage is blocked
let cacheRaw: string | null = null;
let cache: Journey = EMPTY_JOURNEY;

function rawValue(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return memRaw;
  }
}

function read(): Journey {
  const raw = rawValue();
  if (raw !== cacheRaw) {
    cacheRaw = raw;
    try {
      cache = raw ? { ...EMPTY_JOURNEY, ...JSON.parse(raw) } : EMPTY_JOURNEY;
    } catch {
      cache = EMPTY_JOURNEY;
    }
  }
  return cache;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => e.key === KEY && listener();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function updateJourney(patch: Partial<Journey> | ((j: Journey) => Partial<Journey>)) {
  const current = read();
  const next = { ...current, ...(typeof patch === "function" ? patch(current) : patch) };
  const raw = JSON.stringify(next);
  memRaw = raw;
  try {
    localStorage.setItem(KEY, raw);
  } catch {
    // private mode: keep it in memory for this tab
  }
  listeners.forEach((l) => l());
}

export function resetJourney() {
  memRaw = null;
  try {
    localStorage.removeItem(KEY);
  } catch {}
  listeners.forEach((l) => l());
}

export function useJourney(): Journey {
  return useSyncExternalStore(subscribe, read, () => EMPTY_JOURNEY);
}

/** True once the client store has been read (false during SSR and hydration). */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}
