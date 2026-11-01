import type { Question, SnapshotFile, TouchedFile } from "./types";
import { leakFraction, longAddedLines, solutionLeaked } from "./diff";

const SOURCE = /\.(py|js|mjs|cjs|ts|tsx|jsx|go|rb|java|rs|c|cc|cpp|h|hpp|cs|php|kt|swift|scala|lua)$/i;

export type TaskDraft = {
  owner: string;
  name: string;
  language: string;
  stars: number;
  openIssues: number;
  pushedAt: Date | null;
  description: string;
  issueNumber: number;
  title: string;
  body: string;
  htmlUrl: string;
  labels: string[];
  baseSha: string;
  prNumber: number;
  prUrl: string;
  groundTruthDiff: string;
  filesTouched: TouchedFile[];
  difficulty: string;
  readmeExcerpt: string;
  questions: Question[];
  snapshot: SnapshotFile[];
};

export function assessTask(task: TaskDraft): string[] {
  const problems: string[] = [];
  if (!/^[0-9a-f]{40}$/.test(task.baseSha)) problems.push("base SHA is not 40 hex characters");
  if (task.body.trim().length < 40 && task.title.trim().length < 20) {
    problems.push("issue text is too thin");
  }
  if (task.snapshot.length < 2) problems.push("snapshot has fewer than 2 files");
  if (task.snapshot.some((file) => file.content.trim().length === 0)) {
    problems.push("snapshot contains an empty file");
  }
  if (task.snapshot.some((file) => /<!DOCTYPE html>|<html/i.test(file.content.slice(0, 200)))) {
    problems.push("snapshot contains an HTML error page");
  }
  if (!task.snapshot.some((file) => SOURCE.test(file.path) || /^readme/i.test(file.path))) {
    problems.push("snapshot has no source or readme");
  }

  const existing = task.filesTouched.filter((file) => file.status !== "added");
  for (const file of existing) {
    if (!task.snapshot.some((item) => item.path === file.path)) {
      problems.push(`base tree is missing ${file.path}`);
    }
  }

  const additions = task.groundTruthDiff
    .split("\n")
    .filter((line) => line.startsWith("+") && !line.startsWith("+++")).length;
  const deletions = task.groundTruthDiff
    .split("\n")
    .filter((line) => line.startsWith("-") && !line.startsWith("---")).length;
  if (additions + deletions < 1) problems.push("reference diff has no edits");

  if (solutionLeaked(task.groundTruthDiff, task.snapshot.map((file) => file.content))) {
    problems.push(
      `reference lines already appear in the snapshot (${leakFraction(
        task.groundTruthDiff,
        task.snapshot.map((file) => file.content),
      ).toFixed(2)})`,
    );
  }

  if (task.questions.length !== 2) problems.push("expected two comprehension questions");
  for (const question of task.questions) {
    if (!question.prompt.trim() || !question.answerKey.trim()) {
      problems.push(`question ${question.id} is incomplete`);
    }
  }

  const keyBlob = task.questions.map((question) => question.answerKey).join("\n");
  const uniqueFixLines = longAddedLines(task.groundTruthDiff).filter(
    (line) => !task.snapshot.some((file) => file.content.includes(line)),
  );
  if (uniqueFixLines.some((line) => keyBlob.includes(line))) {
    problems.push("an answer key quotes a line that only exists in the fix");
  }

  return problems;
}
