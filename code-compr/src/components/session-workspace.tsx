"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { CodeEditor } from "@/components/code-editor";
import { PHASES, SESSION_MS, type ComprehensionAnswer, type Phase, type QuestionPrompt } from "@/lib/types";

type FileState = { path: string; content: string; original: string };
type ChatMessage = { role: string; content: string };

function formatRemaining(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function SessionWorkspace({
  sessionId,
  repo,
  title,
  issueUrl,
  issueBody,
  readmeExcerpt,
  startedAt,
  status,
  initialPhase,
  questions,
  initialAnswers,
  initialWriteup,
  initialFiles,
  initialMessages,
}: {
  sessionId: string;
  repo: string;
  title: string;
  issueUrl: string;
  issueBody: string;
  readmeExcerpt: string;
  startedAt: string;
  status: string;
  initialPhase: Phase;
  questions: QuestionPrompt[];
  initialAnswers: ComprehensionAnswer[];
  initialWriteup: string;
  initialFiles: FileState[];
  initialMessages: ChatMessage[];
}) {
  const router = useRouter();
  const locked = status !== "active";
  const [phase, setPhase] = useState<Phase>(initialPhase);
  const [files, setFiles] = useState(initialFiles);
  const [active, setActive] = useState(initialFiles[0]?.path ?? "");
  const [answers, setAnswers] = useState<Record<string, string>>(() =>
    Object.fromEntries(initialAnswers.map((answer) => [answer.id, answer.answer])),
  );
  const [writeup, setWriteup] = useState(initialWriteup);
  const [messages, setMessages] = useState(initialMessages);
  const [draft, setDraft] = useState("");
  const [chatError, setChatError] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [newPath, setNewPath] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const saved = useRef(new Map(initialFiles.map((file) => [file.path, file.content])));
  const current = files.find((file) => file.path === active) ?? null;
  const phaseMeta = PHASES.find((item) => item.id === phase) ?? PHASES[0];
  const remaining = Math.max(0, new Date(startedAt).getTime() + SESSION_MS - now);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!current || locked) return;
    if (saved.current.get(current.path) === current.content) return;
    const path = current.path;
    const content = current.content;
    const timer = window.setTimeout(() => {
      void fetch(`/api/sessions/${sessionId}/files`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, content }),
      }).then((response) => {
        if (response.ok) saved.current.set(path, content);
      });
    }, 450);
    return () => window.clearTimeout(timer);
  }, [current, locked, sessionId]);

  const dirty = useMemo(
    () => new Set(files.filter((file) => file.content !== file.original).map((file) => file.path)),
    [files],
  );

  async function saveNotes(nextPhase = phase, nextAnswers = answers, nextWriteup = writeup) {
    await fetch(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        phase: nextPhase,
        comprehensionAnswers: questions.map((question) => ({
          id: question.id,
          answer: nextAnswers[question.id] ?? "",
        })),
        efficiencyWriteup: nextWriteup,
      }),
    });
  }

  async function choosePhase(next: Phase) {
    setPhase(next);
    if (!locked) await saveNotes(next);
  }

  function edit(content: string) {
    setFiles((prev) => prev.map((file) => (file.path === active ? { ...file, content } : file)));
  }

  async function createFile() {
    const path = newPath.trim();
    if (!path || locked) return;
    const response = await fetch(`/api/sessions/${sessionId}/files`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content: "" }),
    });
    if (!response.ok) return;
    setFiles((prev) =>
      prev.some((file) => file.path === path)
        ? prev
        : [...prev, { path, content: "", original: "" }],
    );
    saved.current.set(path, "");
    setActive(path);
    setNewPath("");
  }

  async function send() {
    const message = draft.trim();
    if (!message || streaming || locked) return;
    setDraft("");
    setChatError("");
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setStreaming(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, message }),
      });
      if (!response.ok || !response.body) {
        const data = (await response.json().catch(() => ({}))) as { error?: string };
        setChatError(data.error || "The assistant is unavailable.");
        setStreaming(false);
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";
      let assembled = "";
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        const chunks = pending.split("\n\n");
        pending = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.trim();
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") continue;
          const token = (JSON.parse(payload) as { token?: string }).token ?? "";
          assembled += token;
          const next = assembled;
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: "assistant", content: next };
            return copy;
          });
        }
      }
    } catch {
      setChatError("The assistant connection stopped.");
    } finally {
      setStreaming(false);
    }
  }

  async function submit() {
    if (locked || submitting) return;
    setSubmitting(true);
    setSubmitError("");
    const comprehensionAnswers = questions.map((question) => ({
      id: question.id,
      answer: answers[question.id] ?? "",
    }));
    const response = await fetch(`/api/sessions/${sessionId}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comprehensionAnswers, efficiencyWriteup: writeup }),
    });
    if (!response.ok) {
      setSubmitError("Could not score this round.");
      setSubmitting(false);
      return;
    }
    router.push(`/session/${sessionId}/report`);
  }

  return (
    <div className="flex h-screen flex-col bg-background text-ink">
      <header className="flex items-center justify-between gap-4 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <Link href="/" className="font-mono text-xs text-accent">
            {repo}
          </Link>
          <h1 className="truncate text-lg leading-6">{title}</h1>
        </div>
        <div className="flex items-center gap-3">
          <p className={`font-mono text-sm ${remaining === 0 ? "text-red-800" : "text-ink"}`}>
            {remaining === 0 ? "Time is up" : formatRemaining(remaining)}
          </p>
          {locked ? (
            <a href={`/session/${sessionId}/report`} className="bg-accent text-paper rounded-full px-4 py-2 text-sm">
              View report
            </a>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={submitting}
              className="bg-ink text-paper rounded-full px-4 py-2 text-sm disabled:opacity-60"
            >
              {submitting ? "Scoring…" : "Submit"}
            </button>
          )}
        </div>
      </header>
      {submitError ? <p className="px-4 py-2 text-sm text-red-800">{submitError}</p> : null}

      <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(0,1fr)_380px]">
        <aside className="flex min-h-0 flex-col border-r border-line bg-paper">
          <p className="px-3 py-2 font-mono text-[11px] tracking-wide text-muted uppercase">Files</p>
          <ul className="min-h-0 flex-1 overflow-auto">
            {files.map((file) => (
              <li key={file.path}>
                <button
                  type="button"
                  onClick={() => setActive(file.path)}
                  className={`w-full truncate px-3 py-1.5 text-left font-mono text-xs ${
                    file.path === active ? "bg-accent-soft text-accent" : "text-ink"
                  }`}
                >
                  {dirty.has(file.path) ? "• " : ""}
                  {file.path}
                </button>
              </li>
            ))}
          </ul>
          {locked ? null : (
            <form
              className="flex gap-1 border-t border-line p-2"
              onSubmit={(event) => {
                event.preventDefault();
                void createFile();
              }}
            >
              <input
                value={newPath}
                onChange={(event) => setNewPath(event.target.value)}
                placeholder="path/new-file"
                className="min-w-0 flex-1 rounded border border-line bg-background px-2 py-1 font-mono text-xs"
              />
              <button type="submit" className="font-mono text-xs text-accent">
                Add
              </button>
            </form>
          )}
        </aside>

        <section className="min-h-0 min-w-0 bg-white">
          {current ? (
            <CodeEditor path={current.path} value={current.content} readOnly={locked} onChange={edit} />
          ) : (
            <p className="p-6 text-muted">This snapshot has no files.</p>
          )}
        </section>

        <aside className="flex min-h-0 flex-col border-l border-line bg-paper">
          <div className="flex border-b border-line">
            {PHASES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => void choosePhase(item.id)}
                className={`flex-1 px-2 py-2 font-mono text-xs ${
                  phase === item.id ? "bg-accent text-paper" : "text-muted"
                }`}
              >
                {item.label}
                <span className="block opacity-70">{item.minutes}m</span>
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-3 py-3">
            <p className="mb-3 text-sm text-muted">{phaseMeta.hint}</p>
            {phase === "read" ? (
              <div className="flex flex-col gap-3">
                <a className="text-sm text-accent" href={issueUrl}>
                  Open the GitHub issue
                </a>
                <p className="text-sm leading-6 whitespace-pre-wrap">{issueBody.slice(0, 3500)}</p>
                {readmeExcerpt ? (
                  <pre className="overflow-auto rounded bg-background p-2 font-mono text-[11px] leading-5 whitespace-pre-wrap">
                    {readmeExcerpt}
                  </pre>
                ) : null}
                {questions.map((question) => (
                  <label key={question.id} className="flex flex-col gap-1 text-sm">
                    {question.prompt}
                    <textarea
                      value={answers[question.id] ?? ""}
                      disabled={locked}
                      onChange={(event) =>
                        setAnswers((prev) => ({ ...prev, [question.id]: event.target.value }))
                      }
                      onBlur={() => void saveNotes()}
                      rows={3}
                      className="rounded border border-line bg-background px-2 py-1"
                    />
                  </label>
                ))}
              </div>
            ) : null}
            {phase === "fix" ? (
              <p className="text-sm leading-6">
                Change the files on the left. The assistant can suggest a patch, and you decide what to keep.
                Submit when the bug is fixed and the efficiency note is written.
              </p>
            ) : null}
            {phase === "efficiency" ? (
              <label className="flex flex-col gap-2 text-sm">
                One concrete improvement. Name the file, the cost, and why the change is cheaper.
                <textarea
                  value={writeup}
                  disabled={locked}
                  onChange={(event) => setWriteup(event.target.value)}
                  onBlur={() => void saveNotes(phase, answers, writeup)}
                  rows={10}
                  className="rounded border border-line bg-background px-2 py-1"
                />
              </label>
            ) : null}
          </div>
          <div className="flex h-[46%] min-h-48 flex-col border-t border-line">
            <p className="px-3 py-2 font-mono text-[11px] tracking-wide text-muted uppercase">Assistant</p>
            <div className="min-h-0 flex-1 space-y-2 overflow-auto px-3">
              {messages.length === 0 ? (
                <p className="text-sm text-muted">
                  Ask about a file, a failing case, or whether a suggestion is actually cheaper. Set
                  LLM_API_KEY if the request is refused.
                </p>
              ) : null}
              {messages.map((message, index) => (
                <p key={`${message.role}-${index}`} className="text-sm leading-6 whitespace-pre-wrap">
                  <span className="font-mono text-[11px] text-muted">{message.role}</span>
                  <br />
                  {message.content}
                </p>
              ))}
              {chatError ? <p className="text-sm text-red-800">{chatError}</p> : null}
            </div>
            <form
              className="flex gap-2 border-t border-line p-2"
              onSubmit={(event) => {
                event.preventDefault();
                void send();
              }}
            >
              <input
                value={draft}
                disabled={locked || streaming}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Ask about this code"
                className="min-w-0 flex-1 rounded border border-line bg-background px-2 py-1 text-sm"
              />
              <button type="submit" disabled={locked || streaming} className="font-mono text-xs text-accent">
                Send
              </button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
