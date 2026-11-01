import { prisma } from "../src/lib/db";
import { leakFraction } from "../src/lib/diff";
import { assessTask, type TaskDraft } from "../src/lib/review";
import { scoreWork } from "../src/lib/rubric";
import type { Question, SnapshotFile, TouchedFile } from "../src/lib/types";

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

function checkScorer() {
  const empty = scoreWork({
    questions: [{ id: "bug", prompt: "What breaks?", answerKey: "returns null for an empty list" }],
    answers: [],
    groundTruthDiff: "+    return []\n",
    touchedPaths: ["src/app.py"],
    files: [{ path: "src/app.py", original: "return None\n", content: "return None\n" }],
    efficiencyWriteup: "",
    messages: [],
  });
  assert(empty.comprehension === 1 && empty.fix === 1 && empty.efficiency === 1 && empty.aiFluency === 1, "empty work should score 1s");

  const strong = scoreWork({
    questions: [{ id: "bug", prompt: "What breaks?", answerKey: "returns null for an empty list" }],
    answers: [{ id: "bug", answer: "It returns null when the list is empty." }],
    groundTruthDiff: "+    return []\n+    if not items:\n",
    touchedPaths: ["src/app.py"],
    files: [{
      path: "src/app.py",
      original: "def run(items):\n    return items[0]\n",
      content: "def run(items):\n    if not items:\n        return []\n    return items[0]\n",
    }],
    efficiencyWriteup:
      "src/app.py walks the list twice inside run. Keeping one index lookup avoids the repeated scan and makes the hot path linear instead of doing the work twice.",
    messages: [
      { role: "user", content: "In app.py, what does run return when items is empty? I want to check that before editing." },
      { role: "assistant", content: "It indexes items[0], which fails on an empty list." },
      { role: "user", content: "That matches the issue. I will verify the empty edge by reading the guard again." },
    ],
  });
  assert(strong.comprehension >= 3, `comprehension should be at least 3, got ${strong.comprehension}`);
  assert(strong.fix >= 3, `fix should be at least 3, got ${strong.fix}`);
  assert(strong.efficiency === 4, `efficiency should be 4, got ${strong.efficiency}`);
  assert(strong.aiFluency >= 3, `ai fluency should be at least 3, got ${strong.aiFluency}`);
}

async function main() {
  checkScorer();
  console.log("Scorer checks passed.");

  const tasks = await prisma.task.findMany({
    include: { issue: { include: { repo: true } } },
    orderBy: { issue: { title: "asc" } },
  });

  let ok = 0;
  for (const task of tasks) {
    const snapshot = JSON.parse(task.snapshot) as SnapshotFile[];
    const filesTouched = JSON.parse(task.filesTouched) as TouchedFile[];
    const questions = JSON.parse(task.questions) as Question[];
    const draft: TaskDraft = {
      owner: task.issue.repo.owner,
      name: task.issue.repo.name,
      language: task.issue.repo.language,
      stars: task.issue.repo.stars,
      openIssues: task.issue.repo.openIssues,
      pushedAt: task.issue.repo.pushedAt,
      description: task.issue.repo.description,
      issueNumber: task.issue.number,
      title: task.issue.title,
      body: task.issue.body,
      htmlUrl: task.issue.htmlUrl,
      labels: JSON.parse(task.issue.labels) as string[],
      baseSha: task.baseSha,
      prNumber: task.prNumber,
      prUrl: task.prUrl,
      groundTruthDiff: task.groundTruthDiff,
      filesTouched,
      difficulty: task.difficulty,
      readmeExcerpt: task.readmeExcerpt,
      questions,
      snapshot,
    };
    const problems = assessTask(draft);
    const leak = leakFraction(task.groundTruthDiff, snapshot.map((file) => file.content));
    const label = `${task.issue.repo.owner}/${task.issue.repo.name}#${task.issue.number}`;
    if (problems.length) {
      console.log(`FAIL ${label}: ${problems.join("; ")}`);
      continue;
    }
    ok += 1;
    console.log(`\nOK ${label}`);
    console.log(`  ${task.issue.title}`);
    console.log(`  ${task.issue.htmlUrl}`);
    console.log(`  base ${task.baseSha}  pr #${task.prNumber}  ${task.difficulty}  leak ${leak.toFixed(2)}`);
    console.log(`  files ${snapshot.map((file) => file.path).join(", ")}`);
    console.log(`  touched ${filesTouched.map((file) => `${file.status}:${file.path}`).join(", ")}`);
    console.log(`  issue ${task.issue.body.replace(/\s+/g, " ").slice(0, 180)}`);
    for (const question of questions) {
      console.log(`  Q ${question.prompt}`);
      console.log(`    key ${question.answerKey.replace(/\s+/g, " ").slice(0, 180)}`);
    }
  }

  console.log(`\n${ok}/${tasks.length} tasks passed review.`);
  if (ok < 10) process.exitCode = 1;
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
