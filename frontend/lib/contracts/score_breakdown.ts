// Generated from contracts/score_breakdown.schema.json by `make contracts`. Do not edit.

/**
 * A session's score, computed by backend/scoring from stored runs and events only (no LLM). Stored in scores.breakdown and shown on the report. Holds counts and rates only: no test names, output or other hidden-test data. The same stored records always give the same breakdown.
 */
export interface ScoreBreakdown {
  /**
   * Version of the formulas in backend/scoring that produced this breakdown.
   */
  scoring_version: string;
  tier: "novice" | "adept" | "master";
  /**
   * Novice: mean correctness. Adept/Master: 0.8 × mean correctness + 20 × ai_efficiency.
   */
  final_score: number;
  /**
   * strong ≥ 80, pass ≥ 60, borderline ≥ 45, not_yet below.
   */
  band: "strong" | "pass" | "borderline" | "not_yet";
  mean_correctness: number;
  /**
   * AI efficiency E (Adept/Master). Null for Novice, which has no assistant.
   */
  ai_efficiency: number | null;
  /**
   * One entry per task, in task order.
   */
  tasks: TaskScore[];
}
export interface TaskScore {
  task_id: string;
  kind: "domain" | "dsa";
  visible: TestCounts;
  hidden: TestCounts1;
  /**
   * Share of the counted visible tests that pass: the fail_to_pass ones when rates_over is fail_to_pass, else all. Null when there are none; its weight then goes to the hidden rate.
   */
  visible_rate: number | null;
  /**
   * Same as visible_rate, for the hidden tests.
   */
  hidden_rate: number | null;
  /**
   * The task's time budget. Null when the task has no perf constraint.
   */
  perf_budget_ms: number | null;
  /**
   * Measured runtime on the perf input. Null when there is no perf constraint or nothing was measured.
   */
  perf_ms: number | null;
  /**
   * 1.0 within budget, linear down to 0.5 at 3× budget, 0.5 beyond.
   */
  perf_factor: number;
  /**
   * 100 × (0.3 × visible_rate + 0.7 × hidden_rate) × regression_factor × perf_factor.
   */
  correctness: number;
  /**
   * First focus to last edit on this task. Null without a focus or an edit event.
   */
  time_ms: number | null;
  /**
   * Runs of this task during the session.
   */
  runs: number;
  /**
   * fail_to_pass: the rates count only the tests that fail on the starter (TaskSpec.fail_to_pass), SWE-bench style. all_tests: every test counts; DSA tasks (every case is something to solve) and domain tasks stored without fail_to_pass ids. Absent in breakdowns stored before scoring v2.
   */
  rates_over?: "fail_to_pass" | "all_tests";
  /**
   * Visible fail_to_pass tests passed in the submission. Null unless rates_over is fail_to_pass.
   */
  visible_f2p?: TestCounts2 | null;
  /**
   * Same as visible_f2p, for the hidden tests.
   */
  hidden_f2p?: TestCounts2 | null;
  /**
   * pass_to_pass tests (visible + hidden) still passing in the submission. Null unless rates_over is fail_to_pass.
   */
  pass_to_pass?: TestCounts2 | null;
  /**
   * Share of pass_to_pass tests that still pass: breaking working code costs points. 1.0 without pass_to_pass tests or when rates_over is all_tests.
   */
  regression_factor?: number;
  /**
   * The task certificate's mutation score: how well the task's tests catch bugs. Shown on the report, never affects the score. Null when not measured; absent in breakdowns stored before P2.7.
   */
  mutation_score?: number | null;
}
/**
 * Visible tests passed in the submission.
 */
export interface TestCounts {
  passed: number;
  total: number;
}
/**
 * Hidden tests passed in the submission.
 */
export interface TestCounts1 {
  passed: number;
  total: number;
}
export interface TestCounts2 {
  passed: number;
  total: number;
}
