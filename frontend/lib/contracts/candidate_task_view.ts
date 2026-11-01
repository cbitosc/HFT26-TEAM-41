// Generated from contracts/candidate_task_view.schema.json by `make contracts`. Do not edit.

export type Tier = "novice" | "adept" | "master";
export type Kind = "domain" | "dsa";
/**
 * Relative POSIX path inside the task repo. No leading slash, no . or .. segments.
 */
export type RelPath = string;

/**
 * The part of a TaskSpec the browser may see. Every field here exists in TaskSpec with the same meaning. Never add reference_ref, target_symbols, hidden_tests, hidden DSA cases, certificate or random_seeds.
 */
export interface CandidateTaskView {
  task_id: string;
  version: number;
  tier: Tier;
  kind: Kind;
  runtime: string;
  dsa_tags: string[];
  statement_md: string;
  repo_tour_md: string;
  starter_files: FileMap;
  entry_symbols: string[];
  visible_tests: TestFile[];
  /**
   * Only the visible DSA cases. Null for domain tasks.
   */
  dsa_cases: VisibleDsaCases | null;
  /**
   * The time budget the candidate must meet. The input generator stays on the backend.
   */
  perf: PerfBudget | null;
  time_budget_min: number;
}
/**
 * Relative path -> file content.
 */
export interface FileMap {
  [k: string]: string;
}
export interface TestFile {
  path: RelPath;
  content: string;
}
export interface VisibleDsaCases {
  visible: DsaCase[];
}
/**
 * One DSA test case. input: arguments passed to the entry function; expected: its expected return value. Both may be any JSON value.
 */
export interface DsaCase {
  id: string;
  input: unknown;
  expected: unknown;
}
export interface PerfBudget {
  budget_ms: number;
}
