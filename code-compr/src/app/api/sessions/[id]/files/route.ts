import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

function validPath(path: string): boolean {
  if (!path || path.length > 180) return false;
  if (path.startsWith("/") || path.includes("..") || path.includes("\\")) return false;
  return /^[\w.@/-]+$/.test(path);
}

export async function PUT(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const session = await prisma.session.findUnique({ where: { id } });
  if (!session) return NextResponse.json({ error: "Session not found" }, { status: 404 });
  if (session.status !== "active") {
    return NextResponse.json({ error: "This round is already submitted" }, { status: 409 });
  }

  const body = (await request.json()) as { path?: string; content?: string };
  if (!body.path || !validPath(body.path) || typeof body.content !== "string") {
    return NextResponse.json({ error: "A valid path and content are required" }, { status: 400 });
  }
  const content = body.content.slice(0, 80_000);
  const existing = await prisma.sessionFile.findUnique({
    where: { sessionId_path: { sessionId: id, path: body.path } },
  });
  if (existing) {
    await prisma.sessionFile.update({ where: { id: existing.id }, data: { content } });
  } else {
    await prisma.sessionFile.create({
      data: { sessionId: id, path: body.path, content, original: "" },
    });
  }
  return NextResponse.json({ ok: true });
}
