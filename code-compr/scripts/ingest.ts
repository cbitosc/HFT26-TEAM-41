import { prisma } from "../src/lib/db";
import { buildComprehensionQuestions, readmeExcerpt } from "../src/lib/curate";
import { changedLineCount } from "../src/lib/diff";
import {
  fetchRepoMeta,
  fetchSeedRepos,
  loadClosingPull,
  passesRepoBar,
  searchClosedIssues,
} from "../src/lib/github";
import { assessTask, type TaskDraft } from "../src/lib/review";
import { materializeSnapshot } from "../src/lib/snapshot";

const QUERIES = [
  'label:"good first issue" is:issue is:closed linked:pr',
  "label:beginner is:issue is:closed linked:pr",
  'label:"help wanted" is:issue is:closed linked:pr',
];

const TARGET = 10;

async function saveTask(draft: TaskDraft) {
  const repo = await prisma.repo.upsert({
    where: { owner_name: { owner: draft.owner, name: draft.name } },
    create: {
      owner: draft.owner,
      name: draft.name,
      language: draft.language,
      stars: draft.stars,
      openIssues: draft.openIssues,
      pushedAt: draft.pushedAt,
      description: draft.description,
    },
    update: {
      language: draft.language,
      stars: draft.stars,
      openIssues: draft.openIssues,
      pushedAt: draft.pushedAt,
      description: draft.description,
    },
  });

  const issue = await prisma.issue.upsert({
    where: { repoId_number: { repoId: repo.id, number: draft.issueNumber } },
    create: {
      repoId: repo.id,
      number: draft.issueNumber,
      title: draft.title,
      body: draft.body,
      htmlUrl: draft.htmlUrl,
      state: "closed",
      labels: JSON.stringify(draft.labels),
    },
    update: {
      title: draft.title,
      body: draft.body,
      htmlUrl: draft.htmlUrl,
      labels: JSON.stringify(draft.labels),
    },
  });

  await prisma.task.upsert({
    where: { issueId: issue.id },
    create: {
      issueId: issue.id,
      baseSha: draft.baseSha,
      prNumber: draft.prNumber,
      prUrl: draft.prUrl,
      groundTruthDiff: draft.groundTruthDiff,
      filesTouched: JSON.stringify(draft.filesTouched),
      difficulty: draft.difficulty,
      readmeExcerpt: draft.readmeExcerpt,
      questions: JSON.stringify(draft.questions),
      snapshot: JSON.stringify(draft.snapshot),
    },
    update: {
      baseSha: draft.baseSha,
      prNumber: draft.prNumber,
      prUrl: draft.prUrl,
      groundTruthDiff: draft.groundTruthDiff,
      filesTouched: JSON.stringify(draft.filesTouched),
      difficulty: draft.difficulty,
      readmeExcerpt: draft.readmeExcerpt,
      questions: JSON.stringify(draft.questions),
      snapshot: JSON.stringify(draft.snapshot),
    },
  });
}

async function main() {
  const existing = await prisma.task.count();
  if (existing >= TARGET) {
    console.log(`Catalog already has ${existing} tasks.`);
    return;
  }

  const seeds = await fetchSeedRepos();
  console.log(`Seed list has ${seeds.size} repositories.`);
  let saved = existing;
  const seen = new Set<string>();

  for (const query of QUERIES) {
    if (saved >= TARGET) break;
    for (let page = 1; page <= 4 && saved < TARGET; page += 1) {
      let hits;
      try {
        hits = await searchClosedIssues(query, page);
      } catch (error) {
        console.log(`Search stopped: ${(error as Error).message}`);
        page = 4;
        break;
      }
      if (hits.length === 0) break;
      hits.sort((a, b) => {
        const aSeed = seeds.has(`${a.owner}/${a.name}`.toLowerCase()) ? 0 : 1;
        const bSeed = seeds.has(`${b.owner}/${b.name}`.toLowerCase()) ? 0 : 1;
        return aSeed - bSeed;
      });

      for (const hit of hits) {
        if (saved >= TARGET) break;
        const id = `${hit.owner}/${hit.name}#${hit.number}`;
        if (seen.has(id)) continue;
        seen.add(id);
        process.stdout.write(`consider ${id} … `);
        try {
          const closingResult = await loadClosingPull(hit);
          if ("reason" in closingResult) {
            console.log(`skip (${closingResult.reason})`);
            continue;
          }
          const closing = closingResult.pull;
          const meta = await fetchRepoMeta(hit.owner, hit.name);
          const bar = passesRepoBar(meta);
          if (bar) {
            console.log(`skip (${bar})`);
            continue;
          }
          const snapshot = await materializeSnapshot(hit.owner, hit.name, closing.baseSha, closing.files);
          const body = closing.issueBody || hit.body;
          const draft: TaskDraft = {
            owner: hit.owner,
            name: hit.name,
            language: meta.language,
            stars: meta.stars,
            openIssues: meta.openIssues,
            pushedAt: meta.pushedAt,
            description: meta.description,
            issueNumber: hit.number,
            title: hit.title,
            body,
            htmlUrl: hit.htmlUrl,
            labels: hit.labels,
            baseSha: closing.baseSha,
            prNumber: closing.prNumber,
            prUrl: closing.prUrl,
            groundTruthDiff: closing.groundTruthDiff,
            filesTouched: closing.files,
            difficulty: changedLineCount(closing.files) < 40 ? "easy" : "medium",
            readmeExcerpt: readmeExcerpt(snapshot),
            questions: buildComprehensionQuestions(
              hit.title,
              body,
              snapshot,
              closing.files.filter((file) => file.status !== "added").map((file) => file.path),
            ),
            snapshot,
          };
          const problems = assessTask(draft);
          if (problems.length) {
            console.log(`reject (${problems.join("; ")})`);
            continue;
          }
          await saveTask(draft);
          saved += 1;
          console.log(`saved ${saved}/${TARGET} @ ${closing.baseSha.slice(0, 7)}`);
        } catch (error) {
          const message = (error as Error).message;
          console.log(`error (${message})`);
          if (message.includes("rate limit")) return;
        }
      }
    }
  }

  console.log(`Ingest finished with ${saved} tasks.`);
  if (saved < TARGET) process.exitCode = 1;
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
