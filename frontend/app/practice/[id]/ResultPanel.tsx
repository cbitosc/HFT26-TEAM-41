import type { Example, PracticeResult } from "@/lib/practice";

export type JobState = {
  busy: "run" | "submit" | null;
  result: PracticeResult | null;
  error: string | null;
};

const STATUS_TEXT = {
  timeout: "Time Limit Exceeded: the code was stopped at the time limit. Look for an infinite loop or slow code.",
  oom: "Memory Limit Exceeded: the code used too much memory.",
  error: "Runtime Error: the code could not be run. Check the output below.",
} as const;

function Output({ text }: { text: string }) {
  if (!text) return null;
  return <pre className="mt-2 whitespace-pre-wrap rounded bg-gray-100 p-2 font-mono text-xs">{text}</pre>;
}

export default function ResultPanel({ job, examples }: { job: JobState; examples: Example[] }) {
  const { busy, result, error } = job;
  if (busy) return <p className="p-3 text-sm text-blue-700">{busy === "run" ? "Running…" : "Judging your solution…"}</p>;
  if (error) return <p className="p-3 text-sm text-red-700">Failed: {error}</p>;
  if (!result) return <p className="p-3 text-sm text-gray-500">Run or Submit to see the result.</p>;

  if (result.kind === "submit") {
    return (
      <div className="p-3 text-sm">
        {result.status !== "ok" ? (
          <p className="font-semibold text-red-700">{STATUS_TEXT[result.status]}</p>
        ) : result.accepted ? (
          <p className="text-lg font-semibold text-green-700">Accepted</p>
        ) : (
          <p className="text-lg font-semibold text-red-700">Wrong Answer</p>
        )}
        <p className="mt-1 text-gray-700">
          {result.passed} / {result.total} cases passed · {result.duration_ms} ms
        </p>
        {result.failed_stage === "examples" && (
          <p className="mt-1 text-gray-600">An example case failed, so the hidden cases were not run. Use Run to see which.</p>
        )}
      </div>
    );
  }

  if (result.kind === "custom") {
    return (
      <div className="p-3 text-sm">
        {result.status !== "ok" && <p className="font-semibold text-red-700">{STATUS_TEXT[result.status]}</p>}
        {result.error && <pre className="whitespace-pre-wrap rounded bg-red-50 p-2 font-mono text-xs text-red-900">{result.error}</pre>}
        {result.output !== null && (
          <>
            <div className="text-xs text-gray-600">Output</div>
            <pre className="whitespace-pre-wrap rounded bg-gray-100 p-2 font-mono text-xs">{result.output}</pre>
          </>
        )}
        {(result.stdout || result.stderr) && <Output text={[result.stdout, result.stderr].filter(Boolean).join("\n")} />}
      </div>
    );
  }

  const run = result.result;
  const byId = new Map(examples.map((e, i) => [e.id, { example: e, number: i + 1 }]));
  const allPassed = run.status === "ok" && run.summary.failed === 0;
  return (
    <div className="p-3 text-sm">
      {run.status !== "ok" ? (
        <p className="font-semibold text-red-700">{STATUS_TEXT[run.status]}</p>
      ) : (
        <p className={`font-semibold ${allPassed ? "text-green-700" : "text-red-700"}`}>
          {allPassed ? "All examples passed" : `${run.summary.passed} / ${run.summary.total} examples passed`}
        </p>
      )}
      {run.reason && <p className="text-red-700">{run.reason}</p>}
      <ul className="mt-2 divide-y divide-gray-200 rounded border border-gray-200">
        {run.tests.map((t) => {
          const ex = byId.get(t.id);
          return (
            <li key={t.id} className="px-2 py-1">
              <div className="flex items-center gap-2">
                <span className={t.outcome === "passed" ? "text-green-700" : "text-red-700"}>{t.outcome === "passed" ? "✓" : "✗"}</span>
                <span>Case {ex?.number ?? t.id}</span>
                <span className="ml-auto text-xs text-gray-500">{t.duration_ms} ms</span>
              </div>
              {t.message && <pre className="mt-1 whitespace-pre-wrap rounded bg-red-50 p-2 font-mono text-xs text-red-900">{t.message}</pre>}
            </li>
          );
        })}
      </ul>
      <Output text={[run.stdout_tail, run.stderr_tail].filter(Boolean).join("\n")} />
    </div>
  );
}
