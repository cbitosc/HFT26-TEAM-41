// Candidate telemetry: focus sampled once per second, edits aggregated per second,
// pastes and window blurs. Events are batched and POSTed every 5 s, and with
// sendBeacon when the page is hidden or unloaded. Telemetry never affects the score.
import { API_BASE, ApiError, api } from "./api";
import type { Event } from "./types";

const SAMPLE_MS = 1000;
const FLUSH_MS = 5000;
const MAX_BATCH = 500; // backend MAX_EVENTS_PER_BATCH
const MAX_QUEUE = 5000;

type EditTotals = { added: number; removed: number };

export class Telemetry {
  private queue: Event[] = [];
  private edits = new Map<string, EditTotals>(); // key: taskId \0 file
  private taskId: string | null = null;
  private file: string | null = null;
  private line = 1;
  private editorFocused = false;
  private inFlight = 0; // events at the head of the queue that flush() is sending
  private stopped = true;
  private timers: ReturnType<typeof setInterval>[] = [];

  constructor(private sessionId: string) {}

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.timers = [setInterval(this.sample, SAMPLE_MS), setInterval(() => void this.flush(), FLUSH_MS)];
    window.addEventListener("blur", this.onBlur);
    window.addEventListener("pagehide", this.onPageHide);
    document.addEventListener("visibilitychange", this.onVisibility);
  }

  /** Stop collecting (e.g. after submit or the deadline). Pending events are sent once. */
  stop(): void {
    if (this.stopped) return;
    this.sample();
    this.stopped = true;
    this.timers.forEach(clearInterval);
    window.removeEventListener("blur", this.onBlur);
    window.removeEventListener("pagehide", this.onPageHide);
    document.removeEventListener("visibilitychange", this.onVisibility);
    void this.flush();
  }

  setPosition(taskId: string, file: string, line: number): void {
    this.taskId = taskId;
    this.file = file;
    this.line = Math.max(1, line);
  }

  setEditorFocused(focused: boolean): void {
    this.editorFocused = focused;
  }

  recordEdit(taskId: string, file: string, added: number, removed: number): void {
    if (this.stopped) return;
    const key = `${taskId}\0${file}`;
    const totals = this.edits.get(key) ?? { added: 0, removed: 0 };
    totals.added += added;
    totals.removed += removed;
    this.edits.set(key, totals);
  }

  recordPaste(taskId: string, chars: number): void {
    this.push({ task_id: taskId, type: "paste", payload: { chars } });
  }

  private push(event: { task_id: string } & Pick<Event, "type" | "payload">): void {
    if (this.stopped || this.queue.length >= MAX_QUEUE) return;
    this.queue.push({ ...event, session_id: this.sessionId, ts: Date.now() } as Event);
  }

  // Runs every second: one focus sample, plus that second's edit totals per file.
  private sample = (): void => {
    if (this.editorFocused && document.hasFocus() && this.taskId && this.file) {
      this.push({
        task_id: this.taskId,
        type: "focus",
        payload: { file: this.file, line: this.line, symbol: null },
      });
    }
    for (const [key, totals] of this.edits) {
      const [taskId, file] = key.split("\0");
      this.push({
        task_id: taskId,
        type: "edit",
        payload: { file, symbol: null, chars_added: totals.added, chars_removed: totals.removed },
      });
    }
    this.edits.clear();
  };

  private onBlur = (): void => {
    if (this.taskId) this.push({ task_id: this.taskId, type: "blur", payload: {} });
  };

  private onVisibility = (): void => {
    if (document.visibilityState === "hidden") this.beacon();
  };

  private onPageHide = (): void => this.beacon();

  private async flush(): Promise<void> {
    if (this.inFlight > 0 || this.queue.length === 0) return;
    const batch = this.queue.slice(0, MAX_BATCH);
    this.inFlight = batch.length;
    try {
      await api.postEvents(this.sessionId, batch);
      this.queue.splice(0, batch.length);
    } catch (err) {
      // 4xx (deadline passed, bad event) won't succeed on retry: drop the batch.
      // Network errors and 5xx keep it for the next flush.
      if (err instanceof ApiError && err.status < 500) {
        console.warn("[telemetry] batch dropped:", err.status, err.detail);
        this.queue.splice(0, batch.length);
      }
    } finally {
      this.inFlight = 0;
    }
  }

  // Last-chance send while the page goes away; fetch() may be cancelled at this point.
  private beacon(): void {
    this.sample();
    // Skip events flush() is already sending, so nothing is stored twice.
    const batch = this.queue.slice(this.inFlight, this.inFlight + MAX_BATCH);
    if (batch.length === 0) return;
    const url = `${API_BASE}/sessions/${this.sessionId}/events`;
    const body = new Blob([JSON.stringify(batch)], { type: "application/json" });
    if (!navigator.sendBeacon?.(url, body)) {
      void fetch(url, { method: "POST", body, keepalive: true, headers: { "Content-Type": "application/json" } });
    }
    this.queue.splice(this.inFlight, batch.length);
  }
}
