// All copy-level facts for the showcase live here. Numbers come from docs/PROGRESS.md
// on main (2026-10-31, after P2.7b); change them here, not in the components.

/** Product name. One place to change it. */
export const NAME = "Apollo";

/** The voice interviewer's name. */
export const AGENT = "Athena";

export const TEAM_LINE = "HFT26 Team 41 · JL";
export const EVENT = "CBIT Hacktoberfest '26";
/**
 * The practice-problem app (frontend/ in this repo, needs the backend running). The other
 * two tools, code reading and the AI interview, are pages of this site.
 */
export const PRACTICE_URL = process.env.NEXT_PUBLIC_PRACTICE_URL ?? "http://localhost:3000/practice";

export const REPO_URL = "https://github.com/ROG-user-0987/HFT26-TEAM-41";

export type Status = "built" | "progress" | "planned";

export const STATUS_LABEL: Record<Status, string> = {
  built: "Built",
  progress: "In progress",
  planned: "Planned",
};

/** Real numbers, each with where it comes from. */
export const FACTS = {
  backendTests: 425, // make test, after P2.7
  dockerTests: 55, // make test-docker, after P2.7
  seedTests: 57, // py-fastapi-expenses
  seedLines: 464, // app lines in the seed
  hiddenDomain: 62, // hidden tests in the demo domain task
  hiddenDsa: 30, // hidden DSA cases in the demo
  visibleResultS: 2.59, // median Run → visible result, P1.2b
  e2eBrowserS: 55, // make e2e browser part
  e2eSeedS: 60, // make e2e seed part
  taxonomyTopics: 22, // dsa/taxonomy.yaml
  dsaProblems: 101, // dsa/ bank: 100 imported (LeetCodeDataset) + the P1.3 problem
  mutationCandidates: 17,
  mutationKept: 10,
  mutationChecked: 12,
  llmSpendUsd: 0.000189, // $0.000129 (llm-smoke) + $0.00006 (profiler)
};

export type Stage = {
  id: string;
  title: string;
  body: string;
  status: Status;
  note: string;
};

export const STAGES: Stage[] = [
  {
    id: "portfolio",
    title: "Portfolio",
    body: "The recruiter uploads the candidate's portfolio: JSON Resume plus the DSA topics they say they've solved, with counts.",
    status: "built",
    note: "Contract and 7 fixtures (P0.2, P2.1)",
  },
  {
    id: "profile",
    title: "Profile",
    body: "Keyword rules map stacks, projects and skills to a domain, a runtime, seed concepts and the DSA topics allowed per tier. An LLM is asked only when the rules find nothing, once, with a 150-token cap.",
    status: "built",
    note: "P2.1: rules first; 1 of 7 fixtures needed the LLM",
  },
  {
    id: "tasks",
    title: "Generated tasks",
    body: "A hand-written seed repo is the reference. Novice tasks inject a bug with LibCST mutation operators; Adept tasks stub a whole feature across 2–3 files. The answer is correct by construction: it's the seed.",
    status: "built",
    note: "Novice (P2.2), Adept (P2.3) and Master (P2.4) builders built; DSA bank of 101 problems (P2.6)",
  },
  {
    id: "gate",
    title: "Validation gate",
    body: "Before a task ships: the reference passes, the starter fails, the right tests fail for the right reason, the rest stay green. Each passing task gets a certificate.",
    status: "built",
    note: "P2.7: every demo task is gated by make seed-demo; the AI solve-rate probe (P2.8) is next",
  },
  {
    id: "ide",
    title: "Sandboxed IDE",
    body: "Monaco in the browser, a server-side 60-minute timer, autosave. Every Run starts a fresh container with no network. Visible tests come back in about 2.6 s; hidden tests run in a separate sandbox and are never shown.",
    status: "built",
    note: "P1.2–P1.4b",
  },
  {
    id: "assistant",
    title: "Guarded AI",
    body: "On Adept and Master, an assistant gives hints on a three-step ladder. Input rules and a similarity check against the reference block anything that looks like the answer.",
    status: "planned",
    note: "P3.1–P3.6",
  },
  {
    id: "report",
    title: "Deterministic report",
    body: "Score from stored test results and fixed formulas only. Re-grade recomputes it from the same records and gets the same number, byte for byte.",
    status: "built",
    note: "P1.5: score, band, per-task table, Re-grade",
  },
];

export type Phase = {
  n: number;
  title: string;
  exit: string;
  items: { id: string; name: string; status: Status }[];
};

export const PHASES: Phase[] = [
  {
    n: 0,
    title: "Setup",
    exit: "Repo, contracts, LLM client, runner, first seed",
    items: [
      { id: "P0.0", name: "Repository setup", status: "built" },
      { id: "P0.1", name: "Scaffold", status: "built" },
      { id: "P0.2", name: "Contracts", status: "built" },
      { id: "P0.3", name: "Featherless client", status: "built" },
      { id: "P0.4", name: "Runtimes and runner", status: "built" },
      { id: "P0.5", name: "Seed: py-fastapi-expenses", status: "built" },
    ],
  },
  {
    n: 1,
    title: "Walking skeleton",
    exit: "One task solved, submitted and scored in the browser",
    items: [
      { id: "P1.1", name: "Database and API", status: "built" },
      { id: "P1.2", name: "Worker jobs", status: "built" },
      { id: "P1.2b", name: "Hardening, threat model", status: "built" },
      { id: "P1.3", name: "Demo task", status: "built" },
      { id: "P1.4", name: "Candidate IDE", status: "built" },
      { id: "P1.4b", name: "IDE resilience, bundled Monaco", status: "built" },
      { id: "P1.5", name: "Scoring and report", status: "built" },
      { id: "P1.5b", name: "End-to-end test", status: "built" },
    ],
  },
  {
    n: 2,
    title: "Generation and gate",
    exit: "Two portfolios, two validated assessments",
    items: [
      { id: "P2.1", name: "Taxonomy and profiler", status: "built" },
      { id: "P2.2", name: "Mutation engine (Novice)", status: "built" },
      { id: "P2.3", name: "Feature removal (Adept)", status: "built" },
      { id: "P2.4", name: "Master builder", status: "built" },
      { id: "P2.5", name: "LLM enrichment", status: "built" },
      { id: "P2.6", name: "DSA bank and rewriting", status: "built" },
      { id: "P2.7", name: "Validation gate, certificate", status: "built" },
      { id: "P2.7b", name: "fail_to_pass scoring", status: "built" },
      { id: "P2.8", name: "AI solve-rate probe", status: "planned" },
      { id: "P2.9", name: "Builder pipeline, recruiter page", status: "planned" },
    ],
  },
  {
    n: 3,
    title: "Assistant and scoring",
    exit: "Different AI scores for different behaviour; extraction blocked",
    items: [
      { id: "P3.1", name: "Hint endpoint and ladder", status: "planned" },
      { id: "P3.2", name: "Guards", status: "planned" },
      { id: "P3.3", name: "Assistant panel", status: "planned" },
      { id: "P3.4", name: "AI efficiency score", status: "planned" },
      { id: "P3.5", name: "Simulated candidates", status: "planned" },
      { id: "P3.6", name: "promptfoo attack run", status: "planned" },
    ],
  },
  {
    n: 4,
    title: "Report, Trail Map, interviewer",
    exit: "A real session's report shows every feature",
    items: [
      { id: "P4.1", name: "Certificate view", status: "planned" },
      { id: "P4.2", name: "Claim verification map", status: "planned" },
      { id: "P4.3", name: "Progress timeline, hint ROI", status: "planned" },
      { id: "P4.4", name: "Trail Map builder", status: "planned" },
      { id: "P4.5", name: "Trail Map replay", status: "planned" },
      { id: "P4.6", name: "Integrity flags", status: "planned" },
      { id: "P4.7", name: "Interview plan", status: "planned" },
      { id: "P4.8", name: "Interview turns", status: "planned" },
      { id: "P4.9", name: "Voice in and out", status: "planned" },
      { id: "P4.10", name: "Interview UI", status: "planned" },
      { id: "P4.11", name: "Interview report tab", status: "planned" },
      { id: "P4.12", name: "faster-whisper fallback", status: "planned" },
    ],
  },
  {
    n: 5,
    title: "Polish and demo",
    exit: "Pre-generated data, backup video, rehearsals",
    items: [
      { id: "P5.1", name: "Demo data, cache warm-up", status: "planned" },
      { id: "P5.2", name: "Error handling", status: "planned" },
      { id: "P5.3", name: "Demo checklist, video, README", status: "planned" },
    ],
  },
];

export const TEAM = [
  { name: "Sriram Aditya Sai", role: "Lead" },
  { name: "G Anish", role: "" },
  { name: "Faiz", role: "" },
];
