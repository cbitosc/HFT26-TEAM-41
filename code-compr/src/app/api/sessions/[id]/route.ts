import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import type { ComprehensionAnswer, Phase } from "@/lib/types";

const PHASES = new Set<Phase>(["read", "fix", "efficiency"]);

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const session = await prisma.session.findUnique({ where: { id } });
  if (!session) return NextResponse.json({ error: "Session not found" }, { status: 404 });
  if (session.status !== "active") {
    return NextResponse.json({ error: "This round is already submitted" }, { status: 409 });
  }

  const body = (await request.json()) as {
    phase?: Phase;
    comprehensionAnswers?: ComprehensionAnswer[];
    efficiencyWriteup?: string;
  };

  const data: {
    phase?: string;
    comprehensionAnswers?: string;
    efficiencyWriteup?: string;
  } = {};
  if (body.phase && PHASES.has(body.phase)) data.phase = body.phase;
  if (body.comprehensionAnswers) data.comprehensionAnswers = JSON.stringify(body.comprehensionAnswers);
  if (typeof body.efficiencyWriteup === "string") {
    data.efficiencyWriteup = body.efficiencyWriteup.slice(0, 8000);
  }

  await prisma.session.update({ where: { id }, data });
  return NextResponse.json({ ok: true });
}
