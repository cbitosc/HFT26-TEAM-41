"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { ApiError } from "@/lib/api";
import {
  LANGUAGES,
  type Language,
  type PracticeResult,
  type Problem,
  practiceApi,
} from "@/lib/practice";
import { DifficultyLabel } from "../ProblemList";
import SiteNav from "../SiteNav";
import PracticeEditor from "./PracticeEditor";
import ResultPanel, { type JobState } from "./ResultPanel";

const POLL_MS = 800;
const POLL_LIMIT_MS = 3 * 60_000;

function store(key: string, value?: string): string | null {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch {
    // Private window or blocked storage: the editor still works, it just doesn't remember.
  }
  return null;
}

function errorText(err: unknown): string {
  if (err instanceof ApiError && typeof err.detail === "string") return err.detail;
  if (err instanceof ApiError && Array.isArray(err.detail)) return "invalid request";
  return "could not reach the server";
}

export default function PracticeIDE({ problemId }: { problemId: string }) {
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loadError, setLoadError] = useState("");
  const [language, setLanguage] = useState<Language>("python");
  const [codes, setCodes] = useState<Partial<Record<Language, string>>>({});
  const [bottom, setBottom] = useState<"examples" | "custom" | "result">("examples");
  const [customInput, setCustomInput] = useState("");
  const [job, setJob] = useState<JobState>({ busy: null, result: null, error: null });
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    practiceApi
      .get(problemId)
      .then((p) => {
        const saved = store("practice-language");
        if (saved === "python" || saved === "javascript") setLanguage(saved);
        const initial: Partial<Record<Language, string>> = {};
        for (const { id } of LANGUAGES) {
          initial[id] = store(`practice-code:${p.id}:${id}`) ?? p.languages[id].starter;
        }
        setCodes(initial);
        setCustomInput(JSON.stringify(p.languages.python.examples[0]?.input ?? {}));
        setProblem(p);
      })
      .catch((err) => setLoadError(err instanceof ApiError && err.status === 404 ? "Problem not found." : errorText(err)));
  }, [problemId]);

  const view = problem?.languages[language];
  const code = codes[language] ?? view?.starter ?? "";

  const onCode = useCallback(
    (value: string) => {
      setCodes((c) => ({ ...c, [language]: value }));
      store(`practice-code:${problemId}:${language}`, value);
    },
    [language, problemId],
  );

  function changeLanguage(next: Language) {
    setLanguage(next);
    store("practice-language", next);
  }

  async function poll(jobId: string): Promise<PracticeResult> {
    const started = Date.now();
    while (alive.current && Date.now() - started < POLL_LIMIT_MS) {
      const status = await practiceApi.job(jobId);
      if (status.status === "done" && status.result) return status.result;
      if (status.status === "failed") throw new Error(status.error ?? "job failed");
      await new Promise((r) => setTimeout(r, POLL_MS));
    }
    throw new Error("timed out waiting for the result");
  }

  async function start(kind: "run" | "submit") {
    if (!problem || job.busy) return;
    setBottom("result");
    setJob({ busy: kind, result: null, error: null });
    try {
      const custom = kind === "run" && bottom === "custom" ? customInput : null;
      const { job_id } =
        kind === "run"
          ? await practiceApi.run(problem.id, language, code, custom)
          : await practiceApi.submit(problem.id, language, code);
      const result = await poll(job_id);
      if (alive.current) setJob({ busy: null, result, error: null });
    } catch (err) {
      if (alive.current) setJob({ busy: null, result: null, error: err instanceof Error && !(err instanceof ApiError) ? err.message : errorText(err) });
    }
  }

  if (loadError) {
    return (
      <main className="p-8">
        <p className="mb-3 text-red-700">{loadError}</p>
        <Link href="/practice" className="text-blue-700 underline">
          Back to problems
        </Link>
      </main>
    );
  }
  if (!problem || !view) return <p className="p-8 text-gray-500">Loading problem…</p>;

  const monacoLanguage = LANGUAGES.find((l) => l.id === language)?.monaco ?? "plaintext";

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-gray-200 px-4 py-2 text-sm">
        <Link href="/practice" className="text-blue-700 underline">
          ← Problems
        </Link>
        <h1 className="font-semibold">{problem.title}</h1>
        <DifficultyLabel difficulty={problem.difficulty} />
        <div className="ml-2 border-l border-gray-200 pl-3">
          <SiteNav />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => changeLanguage(e.target.value as Language)}
            aria-label="Language"
            className="rounded border border-gray-300 px-2 py-1"
          >
            {LANGUAGES.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => onCode(view.starter)}
            className="rounded border border-gray-300 px-3 py-1 hover:bg-gray-50"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={() => start("run")}
            disabled={job.busy !== null}
            className="rounded border border-gray-300 px-3 py-1 font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {job.busy === "run" ? "Running…" : "Run"}
          </button>
          <button
            type="button"
            onClick={() => start("submit")}
            disabled={job.busy !== null}
            className="rounded bg-green-600 px-3 py-1 font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {job.busy === "submit" ? "Submitting…" : "Submit"}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <section className="min-h-0 overflow-auto border-gray-200 p-4 lg:w-2/5 lg:border-r">
          <div className="mb-3 flex flex-wrap gap-1 text-xs text-gray-600">
            {problem.tags.map((t) => (
              <span key={t} className="rounded bg-gray-100 px-1.5 py-0.5">
                {t.replaceAll("_", " ")}
              </span>
            ))}
          </div>
          <div className="markdown text-sm">
            <Markdown>{view.statement_md}</Markdown>
          </div>
        </section>

        <section className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-64 flex-1 border-b border-gray-200">
            <PracticeEditor
              modelPath={`practice/${problem.id}/${view.file}`}
              language={monacoLanguage}
              value={code}
              onChange={onCode}
            />
          </div>
          <div className="flex h-64 shrink-0 flex-col">
            <div className="flex gap-4 border-b border-gray-200 px-3 text-sm" role="tablist">
              {(
                [
                  ["examples", "Examples"],
                  ["custom", "Custom input"],
                  ["result", "Result"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={bottom === id}
                  onClick={() => setBottom(id)}
                  className={`border-b-2 py-1.5 ${bottom === id ? "border-blue-600 font-medium" : "border-transparent text-gray-600"}`}
                >
                  {label}
                </button>
              ))}
              <span className="ml-auto py-1.5 text-xs text-gray-500">
                {bottom === "custom" ? "Run uses the custom input" : "Run checks the examples"}
              </span>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              {bottom === "examples" && (
                <ul className="divide-y divide-gray-200 text-sm">
                  {view.examples.map((ex, i) => (
                    <li key={ex.id} className="px-3 py-2">
                      <div className="font-medium">Case {i + 1}</div>
                      <pre className="font-mono text-xs">Input: {JSON.stringify(ex.input)}</pre>
                      <pre className="font-mono text-xs">Expected: {JSON.stringify(ex.expected)}</pre>
                    </li>
                  ))}
                </ul>
              )}
              {bottom === "custom" && (
                <div className="flex h-full flex-col gap-1 p-3">
                  <label htmlFor="custom-input" className="text-xs text-gray-600">
                    A JSON object with these keys: {view.parameters.join(", ")}
                  </label>
                  <textarea
                    id="custom-input"
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    spellCheck={false}
                    className="min-h-0 flex-1 resize-none rounded border border-gray-300 p-2 font-mono text-xs"
                  />
                </div>
              )}
              {bottom === "result" && <ResultPanel job={job} examples={view.examples} />}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
