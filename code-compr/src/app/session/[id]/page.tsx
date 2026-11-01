import { notFound } from "next/navigation";
import { SessionWorkspace } from "@/components/session-workspace";
import { prisma } from "@/lib/db";
import type { ComprehensionAnswer, Phase, Question } from "@/lib/types";

export const instant = false;

export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await prisma.session.findUnique({
    where: { id },
    include: {
      files: { orderBy: { path: "asc" } },
      messages: { orderBy: { createdAt: "asc" } },
      task: { include: { issue: { include: { repo: true } } } },
    },
  });
  if (!session) notFound();

  const questions = (JSON.parse(session.task.questions) as Question[]).map((question) => ({
    id: question.id,
    prompt: question.prompt,
  }));

  return (
    <SessionWorkspace
      sessionId={session.id}
      repo={`${session.task.issue.repo.owner}/${session.task.issue.repo.name}`}
      title={session.task.issue.title}
      issueUrl={session.task.issue.htmlUrl}
      issueBody={session.task.issue.body}
      readmeExcerpt={session.task.readmeExcerpt}
      startedAt={session.startedAt.toISOString()}
      status={session.status}
      initialPhase={session.phase as Phase}
      questions={questions}
      initialAnswers={JSON.parse(session.comprehensionAnswers || "[]") as ComprehensionAnswer[]}
      initialWriteup={session.efficiencyWriteup}
      initialFiles={session.files.map((file) => ({
        path: file.path,
        content: file.content,
        original: file.original,
      }))}
      initialMessages={session.messages.map((message) => ({
        role: message.role,
        content: message.content,
      }))}
    />
  );
}
