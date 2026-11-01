"use client";

// The hint assistant beside the editor (Adept/Master). assistant-ui renders the thread and
// composer; every reply comes from POST /sessions/{id}/tasks/{task}/hint, where the ladder,
// limits and guards live. Messages are kept per task by the IDE for this page visit only.
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { useCallback, useEffect, useState } from "react";
import Markdown from "react-markdown";
import { api, ApiError, type HintStatus } from "@/lib/api";

export type HintMessage = { id: string; role: "user" | "assistant"; text: string };

const LEVEL_NAMES: Record<number, string> = { 1: "concept", 2: "function", 3: "line" };

function convert(message: HintMessage): ThreadMessageLike {
  return { id: message.id, role: message.role, content: [{ type: "text", text: message.text }] };
}

function textOf(message: AppendMessage): string {
  return message.content
    .map((part) => (part.type === "text" ? part.text : ""))
    .join("\n")
    .trim();
}

function MarkdownText({ text }: { text: string }) {
  return (
    <div className="markdown text-sm">
      <Markdown>{text}</Markdown>
    </div>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="mb-3 ml-8 rounded-lg bg-blue-50 px-3 py-2 text-sm" data-testid="hint-question">
      <MessagePrimitive.Parts />
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="mb-3 mr-4 rounded-lg border border-gray-200 bg-white px-3 py-2" data-testid="hint-reply">
      <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
    </MessagePrimitive.Root>
  );
}

export default function AssistantPanel({
  sessionId,
  taskId,
  messages,
  onMessages,
  serverOffset,
  locked,
  runCount,
}: {
  sessionId: string;
  taskId: string;
  messages: HintMessage[];
  onMessages: (taskId: string, update: (prev: HintMessage[]) => HintMessage[]) => void;
  serverOffset: number; // server clock - browser clock, ms
  locked: boolean;
  runCount: number; // finished runs of this task: the ladder may rise after one
}) {
  const [status, setStatus] = useState<HintStatus | null>(null);
  const [asking, setAsking] = useState(false);
  const [now, setNow] = useState(() => Date.now() + serverOffset);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.hintStatus(sessionId, taskId));
    } catch {
      // The panel still works; the status shows again on the next refresh.
    }
  }, [sessionId, taskId]);

  // Load the status for this task, and again after each finished run (the level may rise).
  useEffect(() => {
    let cancelled = false;
    api
      .hintStatus(sessionId, taskId)
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId, taskId, runCount]);

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now() + serverOffset), 1000);
    return () => clearInterval(tick);
  }, [serverOffset]);

  const add = useCallback(
    (message: HintMessage) => onMessages(taskId, (prev) => [...prev, message]),
    [onMessages, taskId],
  );

  const onNew = async (message: AppendMessage) => {
    const question = textOf(message);
    if (!question) return;
    add({ id: `q-${Date.now()}`, role: "user", text: question });
    setAsking(true);
    try {
      const out = await api.hint(sessionId, taskId, question);
      add({ id: `a-${Date.now()}`, role: "assistant", text: out.reply });
      setStatus(out.status);
    } catch (err) {
      const text = err instanceof ApiError && typeof err.detail === "string" ? err.detail : "The assistant is unavailable right now.";
      add({ id: `e-${Date.now()}`, role: "assistant", text: `_${text}_` });
      void refresh();
    } finally {
      setAsking(false);
    }
  };

  const waitS = status && status.next_allowed_ms > now ? Math.ceil((status.next_allowed_ms - now) / 1000) : 0;
  const noneLeft = status?.left === 0;
  const runtime = useExternalStoreRuntime<HintMessage>({
    messages,
    convertMessage: convert,
    onNew,
    isRunning: asking,
    isDisabled: locked || noneLeft,
    isSendDisabled: waitS > 0 || asking,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-full flex-col" data-testid="assistant-panel">
        <div className="shrink-0 border-b border-gray-200 px-3 py-2 text-xs text-gray-600">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-900">Hint assistant</span>
            {status && (
              <span data-testid="hint-level">
                Next: level {status.level} ({LEVEL_NAMES[status.level]}) · {status.left} left
              </span>
            )}
          </div>
          <p className="mt-1">
            Efficient use scores best: run the tests before asking, start from concept hints, and don&apos;t ask for the
            solution.
            {status?.rises_after_run && " The next hint goes deeper after you run the tests."}
          </p>
        </div>
        <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
          <ThreadPrimitive.Viewport className="min-h-0 flex-1 overflow-y-auto bg-gray-50 p-3">
            <ThreadPrimitive.Empty>
              <p className="text-sm text-gray-500">
                Ask about a failing test or where to look. Hints start at the concept level.
              </p>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
            {asking && <p className="text-sm text-gray-500">Thinking…</p>}
          </ThreadPrimitive.Viewport>
          <ComposerPrimitive.Root className="flex shrink-0 gap-2 border-t border-gray-200 p-2">
            <ComposerPrimitive.Input
              placeholder={noneLeft ? "No hints left for this task" : waitS > 0 ? `Next hint in ${waitS} s` : "Ask for a hint…"}
              className="min-h-9 flex-1 resize-none rounded border border-gray-300 px-2 py-1.5 text-sm"
              data-testid="hint-input"
            />
            <ComposerPrimitive.Send
              className="rounded bg-blue-600 px-3 text-sm font-medium text-white disabled:opacity-50"
              data-testid="hint-send"
            >
              Ask
            </ComposerPrimitive.Send>
          </ComposerPrimitive.Root>
        </ThreadPrimitive.Root>
      </div>
    </AssistantRuntimeProvider>
  );
}
