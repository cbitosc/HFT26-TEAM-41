// Ported from code-compr/src/lib/types.ts.

export type Phase = "read" | "fix" | "efficiency";

export type Question = {
  id: string;
  prompt: string;
  answerKey: string;
};

export type SnapshotFile = {
  path: string;
  content: string;
};

export type ComprehensionAnswer = {
  id: string;
  answer: string;
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export const SESSION_MS = 60 * 60 * 1000;

export const PHASES: { id: Phase; label: string; minutes: number; hint: string }[] = [
  {
    id: "read",
    label: "Read",
    minutes: 15,
    hint: "Learn the issue and answer the two checks before editing.",
  },
  {
    id: "fix",
    label: "Fix",
    minutes: 30,
    hint: "Repair the reported bug inside the design that is already here.",
  },
  {
    id: "efficiency",
    label: "Efficiency",
    minutes: 15,
    hint: "Name one real cost in this code and how you would make it cheaper.",
  },
];
