import { prisma } from "@/lib/db";
import { llmConfig, systemPrompt } from "@/lib/llm";

export async function POST(request: Request) {
  const body = (await request.json()) as { sessionId?: string; message?: string };
  const message = body.message?.trim() ?? "";
  if (!body.sessionId || !message) {
    return Response.json({ error: "sessionId and message are required" }, { status: 400 });
  }

  const config = llmConfig();
  const session = await prisma.session.findUnique({
    where: { id: body.sessionId },
    include: {
      files: true,
      messages: { orderBy: { createdAt: "asc" } },
      task: { include: { issue: { include: { repo: true } } } },
    },
  });
  if (!session) return Response.json({ error: "Session not found" }, { status: 404 });
  if (session.status !== "active") {
    return Response.json({ error: "This round is already submitted" }, { status: 409 });
  }

  await prisma.llmMessage.create({
    data: {
      sessionId: session.id,
      role: "user",
      content: message.slice(0, 8000),
      model: config?.model ?? "",
    },
  });

  if (!config) {
    return Response.json(
      { error: "Add LLM_API_KEY to .env to use the assistant. You can still finish the round without it." },
      { status: 400 },
    );
  }

  const history = session.messages.slice(-20).map((item) => ({
    role: item.role,
    content: item.content,
  }));
  const upstream = await fetch(`${config.base}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: config.model,
      stream: true,
      messages: [
        {
          role: "system",
          content: systemPrompt({
            title: session.task.issue.title,
            body: session.task.issue.body,
            repo: `${session.task.issue.repo.owner}/${session.task.issue.repo.name}`,
            files: session.files.map((file) => ({ path: file.path, content: file.content })),
          }),
        },
        ...history,
        { role: "user", content: message.slice(0, 8000) },
      ],
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return Response.json(
      { error: `The assistant request failed (${upstream.status}). ${detail.slice(0, 180)}` },
      { status: 502 },
    );
  }

  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let full = "";

  const stream = new ReadableStream({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) {
        const trimmed = full.trim();
        if (trimmed) {
          await prisma.llmMessage.create({
            data: { sessionId: session.id, role: "assistant", content: trimmed.slice(0, 20000), model: config.model },
          });
        }
        controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
        controller.close();
        return;
      }
      pending += decoder.decode(value, { stream: true });
      const lines = pending.split("\n");
      pending = lines.pop() ?? "";
      for (const line of lines) {
        const payload = line.startsWith("data:") ? line.slice(5).trim() : "";
        if (!payload || payload === "[DONE]") continue;
        try {
          const json = JSON.parse(payload) as {
            choices?: { delta?: { content?: string } }[];
          };
          const token = json.choices?.[0]?.delta?.content ?? "";
          if (!token) continue;
          full += token;
          controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ token })}\n\n`));
        } catch {
          continue;
        }
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
    },
  });
}
