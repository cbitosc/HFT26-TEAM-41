// The two helpers the rubric needs, ported from code-compr/src/lib/diff.ts.

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
