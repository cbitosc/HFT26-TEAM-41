// Practice mode client (backend/app/routes/practice.py). Separate from lib/api.ts, which is
// the assessment session API; here there is no session, only a random id per browser.
import { API_BASE, ApiError } from "./api";
import type { RunResult } from "./types";

export type Difficulty = "easy" | "medium" | "hard";
export type Language = "python" | "javascript";
export const LANGUAGES: { id: Language; label: string; monaco: string }[] = [
  { id: "python", label: "Python 3", monaco: "python" },
  { id: "javascript", label: "JavaScript", monaco: "javascript" },
];

export type ProblemSummary = { id: string; title: string; difficulty: Difficulty; tags: string[] };
export type Example = { id: string; input: Record<string, unknown>; expected: unknown };
export type LanguageView = {
  statement_md: string;
  starter: string;
  file: string;
  examples: Example[];
  parameters: string[];
};
export type Problem = ProblemSummary & { languages: Record<Language, LanguageView> };

export type PracticeResult =
  | { kind: "run"; result: RunResult }
  | {
      kind: "custom";
      status: "ok" | "timeout" | "oom" | "error";
      output: string | null;
      error: string | null;
      duration_ms: number;
      stdout: string;
      stderr: string;
    }
  | {
      kind: "submit";
      status: "ok" | "timeout" | "oom" | "error";
      accepted: boolean;
      passed: number;
      total: number;
      duration_ms: number;
      failed_stage: "examples" | "hidden" | null;
    };

export type PracticeJob = {
  job_id: string;
  status: "queued" | "running" | "done" | "failed";
  result: PracticeResult | null;
  error: string | null;
};

const CLIENT_KEY = "practice-client-id";
let memoryId: string | null = null;

/** A random id per browser, kept in localStorage when it is available. */
export function clientId(): string {
  try {
    let id = localStorage.getItem(CLIENT_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(CLIENT_KEY, id);
    }
    return id;
  } catch {
    memoryId ??= crypto.randomUUID();
    return memoryId;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-Client-Id": clientId() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}/practice${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, data?.detail ?? res.statusText);
  }
  return res.json();
}

export const practiceApi = {
  list: () => request<ProblemSummary[]>("GET", "/problems"),
  get: (id: string) => request<Problem>("GET", `/problems/${id}`),
  run: (id: string, language: Language, code: string, customInput: string | null) =>
    request<{ job_id: string }>("POST", `/problems/${id}/run`, {
      language,
      code,
      custom_input: customInput,
    }),
  submit: (id: string, language: Language, code: string) =>
    request<{ job_id: string }>("POST", `/problems/${id}/submit`, { language, code }),
  job: (jobId: string) => request<PracticeJob>("GET", `/jobs/${jobId}`),
};
