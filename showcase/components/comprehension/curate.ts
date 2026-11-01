// Ported unchanged from code-compr/src/lib/curate.ts: comprehension questions are
// built from the snapshot with plain rules, no model.

import type { Question, SnapshotFile } from "./types";

const SOURCE = /\.(py|js|mjs|cjs|ts|tsx|jsx|go|rb|java|rs|c|cc|cpp|h|hpp|cs|php|kt|swift|scala|lua|qml|r)$/i;

function definedNames(content: string): string[] {
  const names = new Set<string>();
  const pattern = /^\s*(?:async\s+def|def|function|func|fn|sub)\s+([A-Za-z_][\w]*)/gm;
  for (const match of content.matchAll(pattern)) names.add(match[1]);
  const consts = /^\s*(?:const|let|var|public|private|protected)?\s*([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>/gm;
  for (const match of content.matchAll(consts)) names.add(match[1]);
  const cFuncs = /^(?:static\s+)?(?:void|int|char|bool|SEXP|size_t|unsigned|long|double|float|Rboolean)\s+\**\s*([A-Za-z_][\w]*)\s*\(/gm;
  for (const match of content.matchAll(cFuncs)) names.add(match[1]);
  const rFuncs = /^\s*([A-Za-z.][\w.]*)\s*<-\s*function\s*\(/gm;
  for (const match of content.matchAll(rFuncs)) names.add(match[1]);
  return [...names].slice(0, 8);
}

function functionNameAbove(lines: string[], index: number): string {
  for (let i = index; i >= 0 && i > index - 50; i -= 1) {
    const match = lines[i].match(
      /^\s*(?:async\s+def|def|function|func|fn)\s+([A-Za-z_][\w]*)|^\s*(?:const|let)\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?\(/,
    );
    if (match) return match[1] || match[2];
  }
  return "this code";
}

function leadingComment(content: string): string {
  const lines = content.split("\n");
  const kept: string[] = [];
  for (const line of lines.slice(0, 40)) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (kept.length > 0) break;
      continue;
    }
    if (
      trimmed.startsWith("#") ||
      trimmed.startsWith("//") ||
      trimmed.startsWith("/*") ||
      trimmed.startsWith("*") ||
      trimmed.startsWith("'''") ||
      trimmed.startsWith('"""')
    ) {
      kept.push(trimmed.replace(/^[#/*\s"']+|["']+$/g, "").trim());
      continue;
    }
    break;
  }
  return kept.join(" ").replace(/\s+/g, " ").trim();
}

function isEmptyGuard(line: string): boolean {
  return /len\([^)]*\)\s*==\s*0|\.length\s*===?\s*0|\bisEmpty\b|\bis None\b|==\s*None|===?\s*(?:null|undefined)|if\s+not\s+[A-Za-z_][\w.]*\s*:|if\s*\(\s*!\s*[A-Za-z_][\w.]*\s*(?:\.length)?\s*\)/.test(
    line,
  );
}

function behaviorQuestion(file: SnapshotFile): Question | null {
  const lines = file.content.split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const condition = lines[i].trim();
    if (!/^if\b/.test(condition) || !isEmptyGuard(condition)) continue;
    const next = lines.slice(i + 1, i + 4).map((line) => line.trim()).find(Boolean) ?? "";
    const returned = next.match(/^return\b(.*)$/);
    const thrown = next.match(/^(?:raise|throw)\b(.*)$/);
    if (!returned && !thrown) continue;
    const name = functionNameAbove(lines, i);
    if (name === "this code") continue;
    if (returned) {
      const value = returned[1].trim() || "without a value";
      return {
        id: "behavior",
        prompt: `In \`${file.path}\`, what does \`${name}\` do when the input is empty or missing?`,
        answerKey: `The guard \`${condition}\` returns ${value}.`,
      };
    }
    return {
      id: "behavior",
      prompt: `In \`${file.path}\`, when does \`${name}\` stop with an error?`,
      answerKey: `When \`${condition}\`, it fails with ${thrown?.[1].trim() || "an error"}.`,
    };
  }

  const names = definedNames(file.content);
  if (names.length >= 2 || (names.length === 1 && names[0].length > 2)) {
    return {
      id: "behavior",
      prompt: `Which functions or methods are defined in \`${file.path}\`?`,
      answerKey: names.join(", "),
    };
  }

  const comment = leadingComment(file.content);
  if (comment.length > 40 && !/copyright|gnu general|all rights reserved/i.test(comment)) {
    return {
      id: "behavior",
      prompt: `What is \`${file.path}\` responsible for?`,
      answerKey: comment.slice(0, 500),
    };
  }

  return null;
}

function plainText(body: string): string {
  return body
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/<img\b[^>]*>/gi, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export function buildComprehensionQuestions(
  title: string,
  issueBody: string,
  files: SnapshotFile[],
  preferredPaths: string[] = [],
): Question[] {
  const preferred = new Set(preferredPaths);
  const source = files.filter((file) => SOURCE.test(file.path));
  const ordered = [
    ...source.filter((file) => preferred.has(file.path)),
    ...source.filter((file) => !preferred.has(file.path)),
  ];
  const behavior = ordered.map(behaviorQuestion).find(Boolean) ?? null;
  const prose = plainText(issueBody);
  const bug: Question = {
    id: "bug",
    prompt: "What incorrect behavior does the issue report?",
    answerKey: (prose || title).slice(0, 500),
  };

  if (behavior) return [behavior, bug];

  const fallbackFile = ordered[0] ?? files.find((file) => !/^readme/i.test(file.path.split("/").pop() ?? ""));
  const fallback: Question = fallbackFile
    ? {
        id: "behavior",
        prompt: `What does \`${fallbackFile.path}\` contain that is relevant to this issue?`,
        answerKey: leadingComment(fallbackFile.content).slice(0, 500) || definedNames(fallbackFile.content).join(", ") || title,
      }
    : {
        id: "behavior",
        prompt: "Which repository behavior is this issue about?",
        answerKey: title,
      };

  return [fallback, bug];
}

export function readmeExcerpt(files: SnapshotFile[]): string {
  const readme = files.find((file) => /^readme(\.|$)/i.test(file.path.split("/").pop() ?? ""));
  if (!readme) return "";
  return readme.content.slice(0, 1200);
}
