// Ported from code-compr/src/lib/rubric.ts: the deterministic scoreWork only. The
// optional LLM judge and the database write are left out; this page has no server.

import type { ComprehensionAnswer, Question } from "./types";
import { addedPatchLines, novelLines } from "./diff";

export type ScoreDraft = {
  comprehension: number;
  fix: number;
  efficiency: number;
  aiFluency: number;
  comprehensionEvidence: string;
  fixEvidence: string;
  efficiencyEvidence: string;
  aiFluencyEvidence: string;
};

export type Work = {
  questions: Question[];
  answers: ComprehensionAnswer[];
  groundTruthDiff: string;
  touchedPaths: string[];
  files: { path: string; original: string; content: string }[];
  efficiencyWriteup: string;
  messages: { role: string; content: string }[];
};

const STOP = new Set([
  "the", "and", "for", "with", "this", "that", "from", "when", "your", "into",
  "have", "does", "what", "which", "about", "would", "could", "should", "there",
  "their", "then", "than", "been", "being", "were", "was", "are", "is", "it",
  "of", "to", "in", "on", "a", "an",
]);

const MECHANISMS = [
  "cache", "loop", "o(n", "allocat", "batch", "index", "memo", "duplicate",
  "n+1", "query", "recomput", "hash", "linear", "quadratic", "latency",
  "copy", "regex", "compile", "repeat", "once", "lookup", "set ", "map ",
];

function tokens(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9_+#.-]+/)
    .filter((token) => token.length >= 3 && !STOP.has(token));
}

function recall(answer: string, key: string): number {
  const keyTokens = tokens(key);
  if (keyTokens.length === 0) return answer.trim() ? 0.5 : 0;
  const answerTokens = new Set(tokens(answer));
  const hits = keyTokens.filter((token) => answerTokens.has(token)).length;
  return hits / keyTokens.length;
}

function band(value: number, empty: boolean): number {
  if (empty) return 1;
  if (value >= 0.55) return 4;
  if (value >= 0.35) return 3;
  if (value >= 0.15) return 2;
  return 1;
}

function fencedBlocks(text: string): string[] {
  const blocks: string[] = [];
  for (const match of text.matchAll(/```[^\n]*\n([\s\S]*?)```/g)) {
    const body = match[1].trim();
    if (body.length >= 60) blocks.push(body);
  }
  return blocks;
}

function candidateAdded(files: Work["files"]): string[] {
  return files.flatMap((file) => novelLines(file.original, file.content));
}

export function scoreWork(work: Work): ScoreDraft {
  const answers = new Map(work.answers.map((answer) => [answer.id, answer.answer.trim()]));
  const recalls = work.questions.map((question) => recall(answers.get(question.id) ?? "", question.answerKey));
  const average = recalls.length ? recalls.reduce((sum, value) => sum + value, 0) / recalls.length : 0;
  const unanswered = work.questions.every((question) => !(answers.get(question.id) ?? ""));
  const comprehension = band(average, unanswered);

  const added = candidateAdded(work.files);
  const reference = addedPatchLines(work.groundTruthDiff);
  const referenceSet = new Set(reference);
  const overlap = reference.length
    ? added.filter((line) => referenceSet.has(line)).length / reference.length
    : 0;
  const touched = new Set(work.touchedPaths);
  const editedTouched = work.files.some(
    (file) => touched.has(file.path) && file.content !== file.original,
  );
  const meaningful = added.filter((line) => line.length > 2).length >= 2;
  let fix = 1;
  if (editedTouched && overlap >= 0.45) fix = 4;
  else if (editedTouched && (overlap >= 0.2 || meaningful)) fix = 3;
  else if (meaningful || editedTouched) fix = 2;

  const writeup = work.efficiencyWriteup.trim();
  const lower = writeup.toLowerCase();
  const cites = work.files.some((file) => {
    const base = file.path.split("/").pop()?.toLowerCase() ?? "";
    return lower.includes(file.path.toLowerCase()) || (base.length > 3 && lower.includes(base));
  });
  const mechanism = MECHANISMS.some((word) => lower.includes(word));
  let efficiency = 1;
  if (writeup.length >= 80 && cites && mechanism) efficiency = 4;
  else if (writeup.length >= 80 && (cites || mechanism)) efficiency = 3;
  else if (writeup.length >= 40) efficiency = 2;

  const userMessages = work.messages.filter((message) => message.role === "user");
  const assistant = work.messages.filter((message) => message.role === "assistant").map((message) => message.content);
  const specific = userMessages.filter((message) => {
    const text = message.content.toLowerCase();
    return work.files.some((file) => text.includes((file.path.split("/").pop() ?? "").toLowerCase()))
      || /\b(function|line|return|null|empty|edge|why|where)\b/.test(text);
  });
  const verified = userMessages.some((message) =>
    /\b(test|check|verify|wrong|incorrect|fail|reproduce|doesn't|does not|edge)\b/i.test(message.content),
  );
  const pasted = assistant.some((message) =>
    fencedBlocks(message).some((block) =>
      work.files.some((file) => file.content.includes(block) && !file.original.includes(block)),
    ),
  );
  const lazy = userMessages.length === 1
    && userMessages[0].content.trim().length < 40
    && /fix the bug|fix this|solve this|fix the issue/i.test(userMessages[0].content);
  let aiFluency = 1;
  if (userMessages.length === 0 || lazy) aiFluency = 1;
  else if (specific.length >= 2 && verified && !pasted) aiFluency = 4;
  else if (specific.length >= 1 && (verified || userMessages.length >= 2)) aiFluency = 3;
  else aiFluency = 2;
  if (pasted && !verified) aiFluency = Math.min(aiFluency, 2);

  return {
    comprehension,
    fix,
    efficiency,
    aiFluency,
    comprehensionEvidence: unanswered
      ? "No comprehension answers were submitted."
      : `Answer overlap with the stored keys averaged ${Math.round(average * 100)}%.`,
    fixEvidence: added.length === 0
      ? "The snapshot was not edited."
      : `${added.length} new ${added.length === 1 ? "line" : "lines"}, ${Math.round(overlap * 100)}% of the reference added lines, ${editedTouched ? "including" : "not including"} a file the closing change touched. Overlap is a hint; a different correct fix can still score.`,
    efficiencyEvidence: writeup.length === 0
      ? "No efficiency note was submitted."
      : `${writeup.length} characters. ${cites ? "It names a file in the snapshot." : "It does not name a snapshot file."} ${mechanism ? "It names a concrete cost." : "It does not name a concrete cost."}`,
    aiFluencyEvidence: userMessages.length === 0
      ? "The assistant was not used."
      : `${userMessages.length} ${userMessages.length === 1 ? "prompt" : "prompts"}, ${specific.length} ${specific.length === 1 ? "names" : "name"} the code, ${verified ? "with" : "without"} a check of the model, ${pasted ? "and a verbatim paste of model code." : "without a verbatim paste."}`,
  };
}
