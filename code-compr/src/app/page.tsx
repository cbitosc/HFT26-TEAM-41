import { prisma } from "@/lib/db";
import { StartRound } from "@/components/start-round";

export const instant = false;

export default async function Home() {
  const tasks = await prisma.task.findMany({
    include: { issue: { include: { repo: true } } },
    orderBy: { issue: { title: "asc" } },
  });

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-4 border-b border-line pb-8">
        <p className="font-mono text-xs tracking-[0.18em] text-accent uppercase">Practice round</p>
        <h1 className="max-w-3xl text-5xl leading-tight text-ink">Code comprehension</h1>
        <p className="max-w-2xl text-lg leading-8 text-muted">
          Sixty minutes with an unfamiliar open-source snapshot. Read the issue, fix the bug
          inside the existing design, then name one way to make the code cheaper. An LLM can sit
          beside the editor. The score includes how you use it.
        </p>
      </header>

      {tasks.length === 0 ? (
        <p className="text-muted">
          No tasks yet. From this folder, run <code className="font-mono text-ink">npm run ingest</code> with
          network access. A GitHub token in <code className="font-mono text-ink">.env</code> raises the rate limit.
        </p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {tasks.map((task) => {
            const files = JSON.parse(task.filesTouched) as { path: string }[];
            return (
              <li key={task.id} className="grid gap-4 py-5 sm:grid-cols-[1fr_auto] sm:items-center">
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-muted">
                    <span>
                      {task.issue.repo.owner}/{task.issue.repo.name}
                    </span>
                    <span>{task.issue.repo.language || "unknown"}</span>
                    <span>{task.difficulty}</span>
                    <span>
                      {files.length} {files.length === 1 ? "file" : "files"} in the fix
                    </span>
                  </div>
                  <h2 className="text-2xl leading-snug">{task.issue.title}</h2>
                  <a className="text-sm text-accent underline-offset-2 hover:underline" href={task.issue.htmlUrl}>
                    Issue #{task.issue.number}
                  </a>
                </div>
                <StartRound taskId={task.id} />
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
