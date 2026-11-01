// Browser-side API client. Calls go through the /api rewrite in next.config.ts.
import type { CandidateTaskView, Event, RunResult, ScoreBreakdown } from "./types";

export const API_BASE = "/api";

// Response shapes of backend/app/routes (not in contracts/: they are API envelopes).
export type TaskRef = { task_id: string; kind: "domain" | "dsa"; order: number };
export type SessionOut = {
  session_id: string;
  assessment_id: string;
  tier: "novice" | "adept" | "master"; // Adept and Master have the hint assistant
  status: "active" | "expired" | "submitted";
  server_time: string;
  started_at: string;
  deadline_at: string;
  submitted_at: string | null;
  tasks: TaskRef[];
};
export type SavedFiles = {
  snapshot_id: number | null;
  ts: string | null;
  files: Record<string, string> | null; // null: nothing saved yet
};
export type JobView = {
  job_id: string;
  kind: "run" | "submit";
  status: "queued" | "running" | "done" | "failed";
  result: RunResult | null;
  error: string | null;
};

export type HintStatus = {
  level: number; // the next hint's level: 1 concept, 2 function, 3 line
  used: number;
  left: number;
  next_allowed_ms: number; // server time; 0 when a hint can be asked now
  rises_after_run: boolean;
};
export type HintOut = { reply: string; level: number; refused: boolean; blocked: boolean; status: HintStatus };

// GET /sessions/{id}/trail (recruiter key): report-only, never part of the score.
export type TrailNode = {
  id: string; // "path::qualname", or "path" for code outside functions
  file: string;
  name: string;
  target: boolean;
  start: number | null;
  end: number | null;
  dwell_ms: number;
};
export type TrailVisit = { node: string; start_ms: number; end_ms: number; after_hint: boolean };
export type TrailMetrics = {
  time_to_target_ms: number | null;
  off_path_ms: number;
  found: "independent" | "after_hint" | "not_found";
  edit_precision: number | null;
  lines_changed: number;
  functions_visited: number;
  hints: number;
};
export type TaskTrail = {
  task_id: string;
  kind: string;
  targets: string[];
  files: string[];
  nodes: TrailNode[];
  edges: [string, string][];
  visits: TrailVisit[];
  edits: { ts: number; node: string; chars: number }[];
  hints: { ts: number; level: number; blocked: boolean }[];
  metrics: TrailMetrics;
  first_ms: number | null;
  last_ms: number | null;
};
export type TrailOut = { session_id: string; tasks: TaskTrail[] };

// GET /sessions/{id}/report and /report/summary (recruiter key). Shown on the report;
// only the score breakdown is the score.
export type Verdict = "verified" | "partly" | "not_verified" | "not_tested";
export type ReportClaim = {
  claim: string;
  kind: "concept" | "dsa_topic" | "runtime";
  evidence: string;
  tested_by: string[];
  correctness: number | null;
  verdict: Verdict;
};
export type ReportPoint = {
  ts: number;
  minute: number;
  kind: "run" | "submit";
  visible_rate: number | null;
  hidden_rate: number | null;
  hidden_passed: number;
  hidden_total: number;
};
export type ReportDetails = {
  candidate_name: string;
  tier: string;
  breakdown: ScoreBreakdown;
  certificates: { task_id: string; kind: string; certified: boolean; fields: Record<string, unknown> }[];
  claims: ReportClaim[];
  timelines: { task_id: string; points: ReportPoint[]; hints: { ts: number; minute: number; level: number; blocked: boolean }[] }[];
  integrity: {
    pastes: { task_id: string; minute: number; chars: number; large: boolean; after_hint: boolean }[];
    paste_chars: number;
    blurs: number;
    flags: { task_id: string; path: string; line: number; rule: string; excerpt: string }[];
    refused_writes: string[];
    extraction_attempts: number;
  };
  efficiency: {
    value: number;
    parts: { name: string; weight: number; value: number | null; evidence: string }[];
    extraction_attempts: number;
    hints: number;
    scale: number;
  } | null;
};
export type SummaryOut = { summary: string; label: string };

// /interviews/{session id} (F5): the AI voice interview after a submitted session. Never scored.
export type InterviewBlock = "role" | "portfolio" | "submission";
export type InterviewState = {
  status: "planned" | "live" | "done";
  question_index: number;
  question_count: number;
  blocks: InterviewBlock[];
  started_ms: number | null;
  max_seconds: number;
};
export type InterviewTurn = { speaker: "interviewer" | "candidate"; text: string; question_id: string | null; ts: number };
export type InterviewView = { company: string; role: string; state: InterviewState; transcript: InterviewTurn[] };
export type InterviewSay = {
  say_text: string;
  segments: { text: string; audio_url: string }[]; // audio_url is relative to the API
  kind: "question" | "follow_up" | "closing";
  state: InterviewState;
};
export type InterviewSetup = { company: string; role: string; job_description: string; focus: string };
export type InterviewReport = {
  setup: InterviewSetup;
  status: InterviewState["status"];
  consent_at: string | null;
  ended_at: string | null;
  questions: { id: string; block: InterviewBlock; text: string; source: "model" | "template" }[];
  transcript: (InterviewTurn & { kind?: string; llm_used?: boolean })[];
  facts: {
    questions: { question_id: string; task_id: string | null; text: string; facts: { label: string; mentioned: boolean }[] }[];
    mentioned: number;
    total: number;
  };
  tokens: { plan: number; turns: number; budget: number; llm_calls: number };
  label: string;
};

export type ScoreOut = {
  status: "in_progress" | "grading" | "graded"; // in_progress: not submitted yet
  computed_at: string | null;
  breakdown: ScoreBreakdown | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `request failed with ${status}`);
  }
}

async function request<T>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, data?.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  getSession: (id: string) => request<SessionOut>("GET", `/sessions/${id}`),
  getTask: (id: string, taskId: string) => request<CandidateTaskView>("GET", `/sessions/${id}/tasks/${taskId}`),
  getFiles: (id: string, taskId: string) => request<SavedFiles>("GET", `/sessions/${id}/tasks/${taskId}/files`),
  saveFiles: (id: string, taskId: string, files: Record<string, string>) =>
    request<{ snapshot_id: number; ts: string }>("PUT", `/sessions/${id}/tasks/${taskId}/files`, { files }),
  run: (id: string, taskId: string, files: Record<string, string>) =>
    request<{ job_id: string }>("POST", `/sessions/${id}/tasks/${taskId}/run`, { files }),
  submit: (id: string) => request<{ job_id: string }>("POST", `/sessions/${id}/submit`),
  getJob: (jobId: string) => request<JobView>("GET", `/jobs/${jobId}`),
  postEvents: (id: string, events: Event[]) => request<{ accepted: number }>("POST", `/sessions/${id}/events`, events),
  getScore: (id: string) => request<ScoreOut>("GET", `/sessions/${id}/score`),
  regrade: (id: string) => request<ScoreBreakdown>("POST", `/sessions/${id}/regrade`),
  getReport: (id: string, recruiterKey: string) =>
    request<ReportDetails>("GET", `/sessions/${id}/report`, undefined, { "X-Recruiter-Key": recruiterKey }),
  getSummary: (id: string, recruiterKey: string) =>
    request<SummaryOut>("GET", `/sessions/${id}/report/summary`, undefined, { "X-Recruiter-Key": recruiterKey }),
  getTrail: (id: string, recruiterKey: string) =>
    request<TrailOut>("GET", `/sessions/${id}/trail`, undefined, { "X-Recruiter-Key": recruiterKey }),
  getInterview: (id: string) => request<InterviewView>("GET", `/interviews/${id}`),
  startInterview: (id: string) => request<InterviewSay>("POST", `/interviews/${id}/start`, { consent: true }),
  interviewTurn: (id: string, answer_text: string) =>
    request<InterviewSay>("POST", `/interviews/${id}/turn`, { answer_text }),
  endInterview: (id: string) => request<InterviewSay>("POST", `/interviews/${id}/end`),
  setUpInterview: (id: string, setup: InterviewSetup, recruiterKey: string) =>
    request<{ url: string }>("POST", `/interviews/${id}`, setup, { "X-Recruiter-Key": recruiterKey }),
  getInterviewReport: (id: string, recruiterKey: string) =>
    request<InterviewReport>("GET", `/interviews/${id}/report`, undefined, { "X-Recruiter-Key": recruiterKey }),
  hintStatus: (id: string, taskId: string) => request<HintStatus>("GET", `/sessions/${id}/tasks/${taskId}/hints`),
  hint: (id: string, taskId: string, question: string) =>
    request<HintOut>("POST", `/sessions/${id}/tasks/${taskId}/hint`, { question }),
};
