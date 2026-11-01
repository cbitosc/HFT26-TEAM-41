"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { type Difficulty, type ProblemSummary, practiceApi } from "@/lib/practice";
import SiteNav from "./SiteNav";

export const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  easy: "text-green-700",
  medium: "text-amber-600",
  hard: "text-red-700",
};

export function DifficultyLabel({ difficulty }: { difficulty: Difficulty }) {
  return <span className={`font-medium capitalize ${DIFFICULTY_STYLE[difficulty]}`}>{difficulty}</span>;
}

export default function ProblemList() {
  const [problems, setProblems] = useState<ProblemSummary[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty | "all">("all");
  const [tag, setTag] = useState("all");

  useEffect(() => {
    practiceApi
      .list()
      .then(setProblems)
      .catch(() => setError("Could not load the problems. Is the API running?"));
  }, []);

  const tags = useMemo(() => [...new Set((problems ?? []).flatMap((p) => p.tags))].sort(), [problems]);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (problems ?? []).filter(
      (p) =>
        (difficulty === "all" || p.difficulty === difficulty) &&
        (tag === "all" || p.tags.includes(tag)) &&
        (!q || p.title.toLowerCase().includes(q)),
    );
  }, [problems, query, difficulty, tag]);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">Practice problems</h1>
        <SiteNav />
      </div>
      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by title"
          aria-label="Search by title"
          className="min-w-48 flex-1 rounded border border-gray-300 px-2 py-1"
        />
        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value as Difficulty | "all")}
          aria-label="Difficulty"
          className="rounded border border-gray-300 px-2 py-1"
        >
          <option value="all">All difficulties</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <select
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          aria-label="Topic"
          className="rounded border border-gray-300 px-2 py-1"
        >
          <option value="all">All topics</option>
          {tags.map((t) => (
            <option key={t} value={t}>
              {t.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-red-700">{error}</p>}
      {!error && !problems && <p className="text-gray-500">Loading…</p>}
      {problems && (
        <>
          <ul className="divide-y divide-gray-200 rounded border border-gray-200">
            {shown.map((p) => (
              <li key={p.id}>
                <Link href={`/practice/${p.id}`} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50">
                  <span className="flex-1 font-medium">{p.title}</span>
                  <span className="hidden gap-1 text-xs text-gray-500 sm:flex">
                    {p.tags.map((t) => (
                      <span key={t} className="rounded bg-gray-100 px-1.5 py-0.5">
                        {t.replaceAll("_", " ")}
                      </span>
                    ))}
                  </span>
                  <span className="w-16 text-right text-sm">
                    <DifficultyLabel difficulty={p.difficulty} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {shown.length === 0 && <p className="mt-3 text-gray-500">No problems match.</p>}
          <p className="mt-2 text-xs text-gray-500">
            {shown.length} of {problems.length} problems
          </p>
        </>
      )}
    </main>
  );
}
