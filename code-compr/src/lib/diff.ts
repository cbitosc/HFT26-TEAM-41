import type { TouchedFile } from "./types";

const DOC = /\.(md|markdown|rst|txt|adoc)$/i;
const LOCK = /(^|\/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|Gemfile\.lock|go\.sum|poetry\.lock)$/i;

export function parseUnifiedDiff(diff: string): TouchedFile[] {
  const parts = diff.split(/^diff --git /m).slice(1);
  const files: TouchedFile[] = [];

  for (const part of parts) {
    const headerLine = part.split("\n")[0] ?? "";
    const match = headerLine.match(/^a\/(.+?) b\/(.+)$/);
    let path = (match?.[2] ?? "").trim();
    let status: TouchedFile["status"] = "modified";

    if (part.startsWith("a/") && part.includes("\nnew file mode")) status = "added";
    if (part.includes("\nnew file mode")) status = "added";
    else if (part.includes("\ndeleted file mode")) status = "deleted";
    else if (part.includes("\nrename from ")) {
      status = "renamed";
      const from = part.match(/\nrename from (.+)/);
      if (from) path = from[1].trim();
    }

    if (!path || path === "/dev/null") continue;

    let additions = 0;
    let deletions = 0;
    for (const line of part.split("\n")) {
      if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff --git")) continue;
      if (line.startsWith("+")) additions += 1;
      else if (line.startsWith("-")) deletions += 1;
    }

    files.push({ path, status, additions, deletions });
  }

  return files;
}

export function changedLineCount(files: TouchedFile[]): number {
  return files.reduce((sum, file) => sum + file.additions + file.deletions, 0);
}

export function isDocsOnly(files: TouchedFile[]): boolean {
  return files.length > 0 && files.every((file) => DOC.test(file.path));
}

export function isLockOnly(files: TouchedFile[]): boolean {
  return files.length > 0 && files.every((file) => LOCK.test(file.path));
}

export function longAddedLines(diff: string): string[] {
  const lines: string[] = [];
  for (const line of diff.split("\n")) {
    if (!line.startsWith("+") || line.startsWith("+++")) continue;
    const text = line.slice(1).trim();
    if (text.length >= 40 && /[A-Za-z]/.test(text)) lines.push(text);
  }
  return lines;
}

export function leakFraction(diff: string, contents: string[]): number {
  const lines = longAddedLines(diff);
  if (lines.length === 0) return 0;
  const blob = contents.join("\n");
  const hits = lines.filter((line) => blob.includes(line)).length;
  return hits / lines.length;
}

export function solutionLeaked(diff: string, contents: string[]): boolean {
  const lines = longAddedLines(diff);
  const fraction = leakFraction(diff, contents);
  if (lines.length >= 4 && fraction >= 0.5) return true;
  if (lines.length >= 2 && fraction === 1) return true;
  return false;
}

export function addedPatchLines(diff: string): string[] {
  return diff
    .split("\n")
    .filter((line) => line.startsWith("+") && !line.startsWith("+++"))
    .map((line) => line.slice(1).trim())
    .filter((line) => line.length > 0);
}

export function novelLines(before: string, after: string): string[] {
  const old = new Set(
    before
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
  );
  return after
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !old.has(line));
}

export function unifiedDiff(path: string, before: string, after: string): string {
  if (before === after) return "";
  const removed = before.split("\n");
  const added = after.split("\n");
  const body = [
    `diff --git a/${path} b/${path}`,
    `--- a/${path}`,
    `+++ b/${path}`,
    ...removed.map((line) => `-${line}`),
    ...added.map((line) => `+${line}`),
  ];
  return body.join("\n");
}
