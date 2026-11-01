import type { ComprehensionAnswer, Question } from "./types";
import { addedPatchLines, novelLines } from "./diff";
import { prisma } from "./db";

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

function clamp(score: number): number {
  return Math.max(1, Math.min(4, Math.round(score)));
}

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

function parseJudge(text: string): ScoreDraft | null {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;
  try {
    const data = JSON.parse(match[0]) as Partial<ScoreDraft>;
    if (
      typeof data.comprehension !== "number" ||
      typeof data.fix !== "number" ||
      typeof data.efficiency !== "number" ||
      typeof data.aiFluency !== "number"
    ) {
      return null;
    }
    return {
      comprehension: clamp(data.comprehension),
      fix: clamp(data.fix),
      efficiency: clamp(data.efficiency),
      aiFluency: clamp(data.aiFluency),
      comprehensionEvidence: String(data.comprehensionEvidence ?? "").slice(0, 600),
      fixEvidence: String(data.fixEvidence ?? "").slice(0, 600),
      efficiencyEvidence: String(data.efficiencyEvidence ?? "").slice(0, 600),
      aiFluencyEvidence: String(data.aiFluencyEvidence ?? "").slice(0, 600),
    };
  } catch {
    return null;
  }
}

async function judgeWithModel(work: Work, heuristic: ScoreDraft): Promise<ScoreDraft | null> {
  const key = process.env.LLM_API_KEY?.trim();
  if (!key) return null;
  const base = (process.env.LLM_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "");
  const model = process.env.LLM_MODEL || "gpt-4o-mini";
  const prompt = {
    questions: work.questions,
    answers: work.answers,
    efficiencyWriteup: work.efficiencyWriteup.slice(0, 2000),
    touchedPaths: work.touchedPaths,
    heuristic,
    transcript: work.messages.slice(-12).map((message) => ({
      role: message.role,
      content: message.content.slice(0, 1500),
    })),
    candidateAddedLines: candidateAdded(work.files).slice(0, 40),
  };
  const response = await fetch(`${base}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      temperature: 0,
      messages: [
        {
          role: "system",
          content:
            "Score a code-comprehension practice round from 1 to 4 on comprehension, fix, efficiency, and aiFluency. The reference overlap is only a hint. Reward a real bugfix and a specific efficiency claim. Reward prompts that name code and check the model; penalize a blind paste. Reply with JSON only: comprehension, fix, efficiency, aiFluency, comprehensionEvidence, fixEvidence, efficiencyEvidence, aiFluencyEvidence.",
        },
        { role: "user", content: JSON.stringify(prompt) },
      ],
    }),
  });
  if (!response.ok) return null;
  const data = (await response.json()) as { choices?: { message?: { content?: string } }[] };
  return parseJudge(data.choices?.[0]?.message?.content ?? "");
}

export async function scoreSession(sessionId: string): Promise<ScoreDraft> {
  const session = await prisma.session.findUnique({
    where: { id: sessionId },
    include: { files: true, messages: true, task: true },
  });
  if (!session) throw new Error("Session not found");

  const questions = JSON.parse(session.task.questions) as Question[];
  const answers = JSON.parse(session.comprehensionAnswers || "[]") as ComprehensionAnswer[];
  const touched = JSON.parse(session.task.filesTouched) as { path: string }[];
  const work: Work = {
    questions,
    answers,
    groundTruthDiff: session.task.groundTruthDiff,
    touchedPaths: touched.map((file) => file.path),
    files: session.files.map((file) => ({
      path: file.path,
      original: file.original,
      content: file.content,
    })),
    efficiencyWriteup: session.efficiencyWriteup,
    messages: session.messages.map((message) => ({ role: message.role, content: message.content })),
  };
  const heuristic = scoreWork(work);
  const judged = await judgeWithModel(work, heuristic).catch(() => null);
  const draft = judged ?? heuristic;

  await prisma.score.upsert({
    where: { sessionId },
    create: { sessionId, ...draft },
    update: draft,
  });
  return draft;
}
