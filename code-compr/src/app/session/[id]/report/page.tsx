import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import type { Question } from "@/lib/types";

export const instant = false;

const LABELS = [
  ["comprehension", "Comprehension"],
  ["fix", "Fix"],
  ["efficiency", "Efficiency"],
  ["aiFluency", "AI fluency"],
] as const;

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await prisma.session.findUnique({
    where: { id },
    include: { score: true, task: { include: { issue: true } } },
  });
  if (!session) notFound();
  if (!session.score) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p>This round has not been scored yet.</p>
        <Link href={`/session/${id}`} className="text-accent">
          Back to the editor
        </Link>
      </main>
    );
  }

  const questions = JSON.parse(session.task.questions) as Question[];
  const score = session.score;
  const evidence = {
    comprehension: score.comprehensionEvidence,
    fix: score.fixEvidence,
    efficiency: score.efficiencyEvidence,
    aiFluency: score.aiFluencyEvidence,
  };
  const values = {
    comprehension: score.comprehension,
    fix: score.fix,
    efficiency: score.efficiency,
    aiFluency: score.aiFluency,
  };

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <Link href="/" className="font-mono text-xs text-accent">
          Catalog
        </Link>
        <h1 className="text-4xl leading-tight">{session.task.issue.title}</h1>
        <p className="text-muted">Scores are 1–4. The reference patch is a hint, not the only correct fix.</p>
      </header>
      <section className="flex flex-col gap-4">
        {LABELS.map(([key, label]) => (
          <article key={key} className="border-b border-line pb-4">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-2xl">{label}</h2>
              <p className="font-mono text-3xl text-accent">{values[key]}</p>
            </div>
            <p className="mt-2 leading-7 text-muted">{evidence[key]}</p>
          </article>
        ))}
      </section>
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl">Comprehension keys</h2>
        {questions.map((question) => (
          <div key={question.id}>
            <p>{question.prompt}</p>
            <p className="mt-1 text-sm leading-6 text-muted">{question.answerKey}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
