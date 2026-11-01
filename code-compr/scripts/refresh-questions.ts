import { prisma } from "../src/lib/db";
import { buildComprehensionQuestions } from "../src/lib/curate";
import type { SnapshotFile, TouchedFile } from "../src/lib/types";

async function main() {
  const tasks = await prisma.task.findMany({ include: { issue: true } });
  for (const task of tasks) {
    const snapshot = JSON.parse(task.snapshot) as SnapshotFile[];
    const touched = JSON.parse(task.filesTouched) as TouchedFile[];
    const questions = buildComprehensionQuestions(
      task.issue.title,
      task.issue.body,
      snapshot,
      touched.filter((file) => file.status !== "added").map((file) => file.path),
    );
    await prisma.task.update({
      where: { id: task.id },
      data: { questions: JSON.stringify(questions) },
    });
    const blob = snapshot.map((file) => file.content).join("\n");
    if (blob.includes("Preparing snapshot") || blob.includes("code-compr")) {
      console.log(`CONTAMINATED ${task.issue.htmlUrl}`);
    }
  }
  console.log(`Refreshed ${tasks.length} question sets.`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
