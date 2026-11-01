import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function POST(request: Request) {
  const body = (await request.json()) as { taskId?: string };
  if (!body.taskId) return NextResponse.json({ error: "taskId is required" }, { status: 400 });

  const task = await prisma.task.findUnique({ where: { id: body.taskId } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  const snapshot = JSON.parse(task.snapshot) as { path: string; content: string }[];
  const session = await prisma.session.create({
    data: {
      taskId: task.id,
      files: {
        create: snapshot.map((file) => ({
          path: file.path,
          content: file.content,
          original: file.content,
        })),
      },
    },
  });

  return NextResponse.json({ id: session.id });
}
