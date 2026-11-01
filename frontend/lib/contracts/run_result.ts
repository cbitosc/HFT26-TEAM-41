// Generated from contracts/run_result.schema.json by `make contracts`. Do not edit.

/**
 * Result of one sandboxed test run, as reported by a runner container.
 */
export interface RunResult {
  /**
   * ok: the test command ran to completion (tests may still have failed). timeout: killed at the time limit. oom: killed for exceeding the memory limit. error: tests could not be collected or run, or the test command crashed.
   */
  status: "ok" | "timeout" | "error" | "oom";
  /**
   * Why status is error, when the backend knows. test_set_mismatch: the collected test ids differed from the task's expected ids, so no test counts as passed. Null otherwise.
   */
  reason: string | null;
  duration_ms: number;
  tests: TestResult[];
  summary: Summary;
  /**
   * Last part of stdout, truncated by the runner.
   */
  stdout_tail: string;
  /**
   * Last part of stderr, truncated by the runner.
   */
  stderr_tail: string;
}
export interface TestResult {
  /**
   * Runner test id, e.g. a pytest node id.
   */
  id: string;
  name: string;
  outcome: "passed" | "failed" | "error" | "skipped";
  duration_ms: number;
  /**
   * Failure or error message. Null when the test passed.
   */
  message: string | null;
}
/**
 * failed counts both failed and error outcomes; total also counts skipped tests.
 */
export interface Summary {
  passed: number;
  failed: number;
  total: number;
}
