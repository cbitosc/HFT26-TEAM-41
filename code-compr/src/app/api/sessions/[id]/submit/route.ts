import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { scoreSession } from "@/lib/rubric";
import type { ComprehensionAnswer } from "@/lib/types";

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const session = await prisma.session.findUnique({ where: { id }, include: { score: true } });
  if (!session) return NextResponse.json({ error: "Session not found" }, { status: 404 });

  if (session.status === "active") {
    const body = (await request.json().catch(() => ({}))) as {
      comprehensionAnswers?: ComprehensionAnswer[];
      efficiencyWriteup?: string;
    };
    await prisma.session.update({
      where: { id },
      data: {
        status: "submitted",
        submittedAt: new Date(),
        comprehensionAnswers: JSON.stringify(body.comprehensionAnswers ?? []),
        efficiencyWriteup: (body.efficiencyWriteup ?? "").slice(0, 8000),
      },
    });
    await scoreSession(id);
  }

  const score = await prisma.score.findUnique({ where: { sessionId: id } });
  return NextResponse.json({ score });
}
