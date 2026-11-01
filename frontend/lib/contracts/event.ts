// Generated from contracts/event.schema.json by `make contracts`. Do not edit.

/**
 * One entry in a session's event trail. `type` selects the payload shape.
 */
export type Event =
  | RunEvent
  | SubmitEvent
  | HintRequestEvent
  | HintResponseEvent
  | GuardBlockEvent
  | FocusEvent
  | EditEvent
  | PasteEvent
  | BlurEvent;
export type SessionId = string;
export type TaskId = string;
/**
 * Unix epoch time in milliseconds.
 */
export type Timestamp = number;
/**
 * Relative POSIX path inside the task repo. No leading slash, no . or .. segments.
 */
export type RelPath = string;

export interface RunEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "run";
  payload: RunPayload;
}
export interface RunPayload {
  visible: TestCounts;
  hidden_silent: HiddenSilentCounts;
}
export interface TestCounts {
  passed: number;
  total: number;
}
/**
 * Hidden-test results recorded on a run but not shown to the candidate.
 */
export interface HiddenSilentCounts {
  passed: number;
  total: number;
  failing_ids: string[];
}
export interface SubmitEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "submit";
  payload: SubmitPayload;
}
export interface SubmitPayload {
  visible: TestCounts;
  hidden: TestCounts;
  /**
   * Measured runtime on the perf input. Null when the task has no perf constraint.
   */
  perf_ms: number | null;
  /**
   * True for the submission that gets scored.
   */
  final: boolean;
  /**
   * DSA tasks: the hidden cases this session was graded on. Absent or null for domain tasks.
   */
  hidden_sample?: HiddenSample | null;
}
/**
 * Hidden cases sampled from the task's hidden pool for one session. Stored so a re-grade uses exactly the same cases.
 */
export interface HiddenSample {
  seed: number;
  case_ids: string[];
}
export interface HintRequestEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "hint_request";
  payload: HintRequestPayload;
}
export interface HintRequestPayload {
  /**
   * Highest hint level the guard allows for this request.
   */
  level_allowed: number;
  /**
   * The request looked like an attempt to extract the solution.
   */
  flagged_extraction: boolean;
}
export interface HintResponseEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "hint_response";
  payload: HintResponsePayload;
}
export interface HintResponsePayload {
  level: number;
  /**
   * Symbols or files the response mentions.
   */
  mentions: string[];
  /**
   * Similarity of the response to the reference solution.
   */
  similarity: number;
  /**
   * The guard withheld the response.
   */
  blocked: boolean;
}
export interface GuardBlockEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "guard_block";
  payload: GuardBlockPayload;
}
export interface GuardBlockPayload {
  reason: string;
}
export interface FocusEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "focus";
  payload: FocusPayload;
}
export interface FocusPayload {
  file: RelPath;
  line: number;
  symbol: string | null;
}
export interface EditEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "edit";
  payload: EditPayload;
}
export interface EditPayload {
  file: RelPath;
  symbol: string | null;
  chars_added: number;
  chars_removed: number;
}
export interface PasteEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "paste";
  payload: PastePayload;
}
export interface PastePayload {
  chars: number;
}
export interface BlurEvent {
  session_id: SessionId;
  task_id: TaskId;
  ts: Timestamp;
  type: "blur";
  payload: BlurPayload;
}
export interface BlurPayload {}
