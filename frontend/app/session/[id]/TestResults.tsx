import type { RunResult } from "@/lib/types";

export type TaskRunState = {
  running: boolean;
  result: RunResult | null;
  error: string | null;
};

const STATUS_TEXT: Record<Exclude<RunResult["status"], "ok">, string> = {
  timeout: "The tests were stopped at the time limit. Look for an infinite loop or very slow code.",
  oom: "The tests were stopped for using too much memory.",
  error: "The tests could not be collected or run. Check the output below for a syntax or import error.",
};

const REASON_TEXT: Record<string, string> = {
  test_set_mismatch:
    "The tests that ran did not match the task's tests, so none count as passed. Tests can't be added, removed or renamed.",
};

export default function TestResults({ state }: { state: TaskRunState | undefined }) {
  if (!state || (!state.running && !state.result && !state.error)) {
    return <p className="p-3 text-sm text-gray-500">Press Run to run the visible tests.</p>;
  }
  const { result } = state;
  return (
    <div className="flex h-full flex-col overflow-auto p-3 text-sm">
      <div className="mb-2 flex items-center gap-3">
        {result && (
          <span className={result.summary.failed === 0 && result.status === "ok" ? "font-semibold text-green-700" : "font-semibold text-red-700"}>
            {result.summary.passed}/{result.summary.total} passed
          </span>
        )}
        {result && <span className="text-gray-500">{result.duration_ms} ms</span>}
        {state.running && <span className="text-blue-700">{result ? "Finishing run…" : "Running tests…"}</span>}
      </div>
      {state.error && <p className="mb-2 text-red-700">Run failed: {state.error}</p>}
      {result && result.status !== "ok" && <p className="mb-2 text-red-700">{STATUS_TEXT[result.status]}</p>}
      {result?.reason && <p className="mb-2 text-red-700">{REASON_TEXT[result.reason] ?? result.reason}</p>}
      {result && (
        <ul className="divide-y divide-gray-200 rounded border border-gray-200">
          {result.tests.map((t) => (
            <li key={t.id} className="px-2 py-1">
              <div className="flex items-center gap-2">
                <span className={t.outcome === "passed" ? "text-green-700" : t.outcome === "skipped" ? "text-gray-500" : "text-red-700"}>
                  {t.outcome === "passed" ? "✓" : t.outcome === "skipped" ? "–" : "✗"}
                </span>
                <span className="font-mono">{t.name}</span>
                <span className="ml-auto text-xs text-gray-500">{t.outcome}</span>
              </div>
              {t.message && <pre className="mt-1 whitespace-pre-wrap rounded bg-red-50 p-2 font-mono text-xs text-red-900">{t.message}</pre>}
            </li>
          ))}
        </ul>
      )}
      {result && (result.stdout_tail || result.stderr_tail) && (
        <details className="mt-2">
          <summary className="cursor-pointer text-gray-600">Output</summary>
          <pre className="mt-1 whitespace-pre-wrap rounded bg-gray-100 p-2 font-mono text-xs">
            {[result.stdout_tail, result.stderr_tail].filter(Boolean).join("\n")}
          </pre>
        </details>
      )}
    </div>
  );
}
