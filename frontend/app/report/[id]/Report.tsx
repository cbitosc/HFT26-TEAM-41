"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type ScoreOut } from "@/lib/api";
import type { ScoreBreakdown, TaskScore, TestCounts } from "@/lib/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import InsightsTab from "./InsightsTab";
import InterviewTab from "./InterviewTab";
import TrailTab from "./TrailTab";

const POLL_MS = 2000;

const BAND: Record<ScoreBreakdown["band"], { label: string; className: string }> = {
  strong: { label: "Strong", className: "bg-green-100 text-green-800" },
  pass: { label: "Pass", className: "bg-blue-100 text-blue-800" },
  borderline: { label: "Borderline", className: "bg-amber-100 text-amber-900" },
  not_yet: { label: "Not yet", className: "bg-gray-200 text-gray-800" },
};

function pct(rate: number | null): string {
  return rate === null ? "no tests" : `${Math.round(rate * 100)}%`;
}

function duration(ms: number | null): string {
  if (ms === null) return "—";
  const s = Math.round(ms / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s` : `${s}s`;
}

// fail_to_pass tasks count only the tests the starter failed ("fixed k/n"); others all tests.
function counted(f2p: TestCounts | null | undefined, rate: number | null): string {
  if (!f2p) return pct(rate);
  return f2p.total === 0 ? "nothing to fix" : `fixed ${f2p.passed}/${f2p.total}`;
}

function mutation(score: number | null | undefined): string {
  return score === null || score === undefined ? "not measured" : `${Math.round(score * 100)}%`;
}

function TaskRow({ task, index }: { task: TaskScore; index: number }) {
  return (
    <tr data-testid="task-row" data-task-id={task.task_id} className="border-t border-gray-200">
      <td className="py-2 pr-4">
        <div className="font-medium">
          {index + 1}. {task.kind === "dsa" ? "DSA" : "Domain"} task
        </div>
        <div className="text-xs text-gray-500">{task.task_id}</div>
      </td>
      <td className="py-2 pr-4 tabular-nums" data-field="visible">
        {task.visible.passed}/{task.visible.total}{" "}
        <span className="text-gray-500">({counted(task.visible_f2p, task.visible_rate)})</span>
      </td>
      <td className="py-2 pr-4 tabular-nums" data-field="hidden">
        {task.hidden.passed}/{task.hidden.total}{" "}
        <span className="text-gray-500">({counted(task.hidden_f2p, task.hidden_rate)})</span>
      </td>
      <td className="py-2 pr-4 tabular-nums" data-field="correctness">
        {task.correctness.toFixed(2)}
        {task.pass_to_pass && task.pass_to_pass.total > 0 && (
          <div className="text-xs text-gray-500" data-field="regression">
            regression ×{(task.regression_factor ?? 1).toFixed(2)} ({task.pass_to_pass.passed}/{task.pass_to_pass.total}{" "}
            still pass)
          </div>
        )}
        {task.perf_budget_ms !== null && (
          <div className="text-xs text-gray-500">
            perf ×{task.perf_factor.toFixed(2)} ({task.perf_ms ?? "—"} / {task.perf_budget_ms} ms)
          </div>
        )}
      </td>
      <td className="py-2 pr-4 tabular-nums" data-field="time">
        {duration(task.time_ms)}
      </td>
      <td className="py-2 pr-4 tabular-nums" data-field="runs">
        {task.runs}
      </td>
      <td className="py-2 tabular-nums" data-field="mutation">
        {mutation(task.mutation_score)}
      </td>
    </tr>
  );
}

export default function Report({ sessionId }: { sessionId: string }) {
  const [score, setScore] = useState<ScoreOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [regrade, setRegrade] = useState<"idle" | "running" | "same" | "changed" | "failed">("idle");
  const [tab, setTab] = useState("score");

  const load = useCallback(async () => {
    try {
      const next = await api.getScore(sessionId);
      setScore(next);
      setError(null);
      return next.status === "graded";
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? "This session does not exist." : "Could not reach the server.");
      return err instanceof ApiError && err.status === 404;
    }
  }, [sessionId]);

  // Poll until the submit job has stored a score.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const done = await load();
      if (!stopped && !done) timer = setTimeout(tick, POLL_MS);
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [load]);

  const onRegrade = async () => {
    const before = JSON.stringify(score?.breakdown);
    setRegrade("running");
    try {
      const after = await api.regrade(sessionId);
      setRegrade(JSON.stringify(after) === before ? "same" : "changed");
      await load();
    } catch {
      setRegrade("failed");
    }
  };

  if (error) return <p className="p-8 text-red-700">{error}</p>;
  if (!score) return <p className="p-8 text-gray-500">Loading report…</p>;
  if (score.status !== "graded" || !score.breakdown) {
    return (
      <p className="p-8 text-gray-600" data-testid="report-status">
        {score.status === "grading" ? "Grading the submission…" : "This session has not been submitted yet."}
      </p>
    );
  }

  const b = score.breakdown;
  const band = BAND[b.band];
  return (
    <main className={`mx-auto p-8 text-gray-900 ${tab === "score" ? "max-w-4xl" : "max-w-6xl"}`}>
      <header className="mb-6 flex flex-wrap items-baseline gap-3">
        <h1 className="text-2xl font-semibold">Assessment report</h1>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs uppercase text-gray-600">{b.tier}</span>
        <span className="text-sm text-gray-500">
          Scored {score.computed_at ? new Date(score.computed_at).toLocaleString() : ""} · scoring v{b.scoring_version}
        </span>
      </header>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="score" data-testid="tab-score">
            Score
          </TabsTrigger>
          <TabsTrigger value="insights" data-testid="tab-insights">
            Insights
          </TabsTrigger>
          <TabsTrigger value="trail" data-testid="tab-trail">
            Trail Map
          </TabsTrigger>
          <TabsTrigger value="interview" data-testid="tab-interview">
            Interview
          </TabsTrigger>
        </TabsList>
        <TabsContent value="interview">
          <InterviewTab sessionId={sessionId} />
        </TabsContent>
        <TabsContent value="insights">
          <InsightsTab sessionId={sessionId} />
        </TabsContent>
        <TabsContent value="trail">
          <TrailTab sessionId={sessionId} />
        </TabsContent>
        <TabsContent value="score">

      <section className="mb-8 flex flex-wrap items-center gap-6 rounded-lg border border-gray-200 p-6">
        <div>
          <div className="text-sm text-gray-500">Final score</div>
          <div className="text-5xl font-semibold tabular-nums" data-testid="final-score">
            {b.final_score.toFixed(2)}
          </div>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-semibold ${band.className}`} data-testid="band">
          {band.label}
        </span>
        <div className="text-sm text-gray-600">
          <div>Mean correctness: {b.mean_correctness.toFixed(2)}</div>
          {b.ai_efficiency !== null && <div>AI efficiency: {(b.ai_efficiency * 100).toFixed(0)}%</div>}
        </div>
        <div className="ml-auto text-right">
          <button
            onClick={onRegrade}
            disabled={regrade === "running"}
            className="rounded border border-gray-300 px-4 py-1.5 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {regrade === "running" ? "Re-grading…" : "Re-grade"}
          </button>
          <div className="mt-1 text-xs text-gray-500" data-testid="regrade-status">
            {regrade === "same" && "Re-graded from stored records: identical score."}
            {regrade === "changed" && "Re-graded: the score changed."}
            {regrade === "failed" && "Re-grade failed."}
          </div>
        </div>
      </section>

      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-gray-500">
          <tr>
            <th className="pb-2 pr-4 font-semibold">Task</th>
            <th className="pb-2 pr-4 font-semibold">Visible tests</th>
            <th className="pb-2 pr-4 font-semibold">Hidden tests</th>
            <th className="pb-2 pr-4 font-semibold">Correctness</th>
            <th className="pb-2 pr-4 font-semibold">Time</th>
            <th className="pb-2 pr-4 font-semibold">Runs</th>
            <th className="pb-2 font-semibold" title="Share of reference mutants the task's hidden tests catch">
              Mutation score
            </th>
          </tr>
        </thead>
        <tbody>
          {b.tasks.map((task, i) => (
            <TaskRow key={task.task_id} task={task} index={i} />
          ))}
        </tbody>
      </table>
      <p className="mt-4 text-xs text-gray-500">
        Correctness = 100 × (0.3 × visible rate + 0.7 × hidden rate) × regression × perf factor. Rates count the
        tests that failed on the starter (&quot;fixed&quot;); regression = share of already-passing tests still passing.
        DSA: every case counts. Time: first focus to last edit.
        Bands: Strong ≥ 80, Pass ≥ 60, Borderline ≥ 45. Mutation score: how well the task&apos;s tests catch
        bugs (task quality, not part of the score).
      </p>
        </TabsContent>
      </Tabs>
    </main>
  );
}
