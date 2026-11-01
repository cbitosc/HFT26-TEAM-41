"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import Chip from "@/components/Chip";
import { NAME } from "@/lib/site";
import { scriptedReply } from "./assistant";
import { scoreWork, type ScoreDraft } from "./rubric";
import { TASK } from "./task";
import { PHASES, SESSION_MS, type ChatMessage, type Phase } from "./types";

// Browser-only port of code-compr's practice round: same flow (read the issue and
// answer two checks, fix the bug in an unfamiliar snapshot, write one efficiency
// note, with an assistant beside the editor), same questions (curate.ts) and same
// heuristic rubric (scoreWork). The database, GitHub ingest and model calls are
// replaced by one bundled task and a scripted assistant.

type FileState = { path: string; content: string; original: string };
type Stage = "intro" | "work" | "report";

const LABELS = [
  ["comprehension", "Comprehension"],
  ["fix", "Fix"],
  ["efficiency", "Efficiency"],
  ["aiFluency", "AI fluency"],
] as const;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function formatRemaining(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function freshFiles(): FileState[] {
  return TASK.snapshot.map((file) => ({ path: file.path, content: file.content, original: file.content }));
}

export default function Comprehension() {
  const [stage, setStage] = useState<Stage>("intro");
  const [phase, setPhase] = useState<Phase>("read");
  const [files, setFiles] = useState(freshFiles);
  const [active, setActive] = useState("pagekit/paginate.py");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [writeup, setWriteup] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(0);
  const [score, setScore] = useState<ScoreDraft | null>(null);
  const chatList = useRef<HTMLDivElement>(null);

  const current = files.find((file) => file.path === active) ?? null;
  const phaseMeta = PHASES.find((item) => item.id === phase) ?? PHASES[0];
  const remaining = Math.max(0, startedAt + SESSION_MS - now);
  const dirty = useMemo(
    () => new Set(files.filter((file) => file.content !== file.original).map((file) => file.path)),
    [files],
  );

  useEffect(() => {
    if (stage !== "work") return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [stage]);

  // Scroll only the message list; scrollIntoView would also scroll the page on phones.
  useEffect(() => {
    const list = chatList.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages]);

  function start() {
    const t = Date.now();
    setStartedAt(t);
    setNow(t);
    setStage("work");
    window.scrollTo(0, 0);
  }

  function edit(content: string) {
    setFiles((prev) => prev.map((file) => (file.path === active ? { ...file, content } : file)));
  }

  async function send() {
    const message = draft.trim();
    if (!message || streaming) return;
    setDraft("");
    setMessages((prev) => [...prev, { role: "user", content: message }, { role: "assistant", content: "" }]);
    setStreaming(true);
    await sleep(450);
    // Reveal the canned reply a few words at a time, like a streamed response.
    const words = scriptedReply(message).split(/(?<= )/);
    let assembled = "";
    for (let i = 0; i < words.length; i += 3) {
      assembled += words.slice(i, i + 3).join("");
      const next = assembled;
      setMessages((prev) => [...prev.slice(0, -1), { role: "assistant", content: next }]);
      await sleep(28);
    }
    setStreaming(false);
  }

  function submit() {
    setScore(
      scoreWork({
        questions: TASK.questions,
        answers: TASK.questions.map((question) => ({ id: question.id, answer: answers[question.id] ?? "" })),
        groundTruthDiff: TASK.groundTruthDiff,
        touchedPaths: TASK.touchedPaths,
        files,
        efficiencyWriteup: writeup,
        messages,
      }),
    );
    setStage("report");
    window.scrollTo(0, 0);
  }

  function again() {
    setFiles(freshFiles());
    setActive("pagekit/paginate.py");
    setAnswers({});
    setWriteup("");
    setMessages([]);
    setPhase("read");
    setScore(null);
    setStage("intro");
    window.scrollTo(0, 0);
  }

  return (
    <div className={`cc${stage === "work" ? " dark" : ""}`}>
      <header className="cc-top">
        <div className="wrap cc-top-in">
          <Link href="/" className="hdr-mark">
            {NAME}
          </Link>
          <span className="cc-crumb">Code comprehension, practice</span>
          {stage === "work" ? (
            <>
              <span className="cc-timer" role="timer" aria-label="Time remaining" data-up={remaining === 0}>
                {remaining === 0 ? "Time is up" : formatRemaining(remaining)}
              </span>
              <button type="button" className="cc-submit" onClick={submit}>
                Submit
              </button>
            </>
          ) : (
            <Link href="/" className="cc-back">
              Back to the site
            </Link>
          )}
        </div>
      </header>

      {stage === "intro" && (
        <main className="wrap cc-intro">
          <div className="cc-intro-text">
            <p className="label">Code comprehension</p>
            <h1 className="h2">Read code you didn&apos;t write, then fix it.</h1>
            <p>
              Sixty minutes with an unfamiliar snapshot. Read the issue, fix the bug inside the existing design, then
              name one way to make the code cheaper. An assistant sits beside the editor, and the score includes how
              you use it.
            </p>
            <Chip s="progress">Browser demo, no model calls</Chip>
            <p className="small cc-credit">
              One bundled task and a scripted assistant. Questions and rubric are ported unchanged from the
              team&apos;s code-compr app, which ingests closed GitHub issues with a linked PR and uses the PR as the
              reference.
            </p>
          </div>

          <article className="cc-task">
            <p className="small">
              {TASK.repo}, {TASK.language}, 1 file in the fix
            </p>
            <h2 className="h3">{TASK.title}</h2>
            <p className="small">Issue #{TASK.issueNumber}</p>
            <ol className="cc-steps">
              {PHASES.map((item) => (
                <li key={item.id}>
                  <span className="cc-step-name">
                    {item.label} <span className="muted">{item.minutes} min</span>
                  </span>
                  <span className="small">{item.hint}</span>
                </li>
              ))}
            </ol>
            <p className="small">
              Scores are 1 to 4 on comprehension, fix, efficiency and AI fluency, from plain rules: word overlap with the
              answer keys, overlap with the reference patch, whether your note names a file and a cost, and whether your
              prompts name the code and check the answer. Nothing leaves this tab.
            </p>
            <button type="button" className="cc-start" onClick={start}>
              Start the round
            </button>
          </article>
        </main>
      )}

      {stage === "work" && (
        <main className="cc-ws">
          <aside className="cc-files" aria-label="Files">
            <p className="cc-pane-title">Files</p>
            <ul>
              {files.map((file) => (
                <li key={file.path}>
                  <button
                    type="button"
                    onClick={() => setActive(file.path)}
                    aria-current={file.path === active}
                  >
                    {file.path}
                    {dirty.has(file.path) && <i aria-label="edited" />}
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="cc-editor" aria-label="Editor">
            {current && <CodeArea key={current.path} path={current.path} value={current.content} onChange={edit} />}
          </section>

          <aside className="cc-side">
            <div className="cc-tabs" role="tablist">
              {PHASES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={phase === item.id}
                  onClick={() => setPhase(item.id)}
                >
                  {item.label}
                  <span>{item.minutes}m</span>
                </button>
              ))}
            </div>
            <div className="cc-phase">
              <p className="small">{phaseMeta.hint}</p>
              {phase === "read" && (
                <>
                  <h2 className="cc-issue-title">{TASK.title}</h2>
                  <p className="cc-issue">{TASK.issueBody}</p>
                  {TASK.readmeExcerpt && <pre className="cc-readme">{TASK.readmeExcerpt}</pre>}
                  {TASK.questions.map((question) => (
                    <label key={question.id} className="cc-q">
                      <Prompt text={question.prompt} />
                      <textarea
                        rows={3}
                        value={answers[question.id] ?? ""}
                        onChange={(e) => setAnswers((prev) => ({ ...prev, [question.id]: e.target.value }))}
                      />
                    </label>
                  ))}
                </>
              )}
              {phase === "fix" && (
                <p className="cc-note">
                  Change the files on the left. The assistant can suggest a patch, and you decide what to keep. Submit
                  when the bug is fixed and the efficiency note is written.
                </p>
              )}
              {phase === "efficiency" && (
                <label className="cc-q">
                  One concrete improvement. Name the file, the cost, and why the change is cheaper.
                  <textarea rows={9} value={writeup} onChange={(e) => setWriteup(e.target.value)} />
                </label>
              )}
            </div>

            <div className="cc-chat">
              <p className="cc-pane-title">Assistant</p>
              <div className="cc-msgs" aria-live="polite" ref={chatList}>
                {messages.length === 0 && (
                  <p className="small">
                    Ask about a file, a failing case, or whether a suggestion is actually cheaper. Replies here are
                    scripted.
                  </p>
                )}
                {messages.map((message, index) => (
                  <div key={index} className="cc-msg" data-r={message.role}>
                    <span>{message.role === "user" ? "You" : "Assistant"}</span>
                    <Reply text={message.content} />
                  </div>
                ))}
              </div>
              <form
                className="cc-ask"
                onSubmit={(e) => {
                  e.preventDefault();
                  void send();
                }}
              >
                <input
                  value={draft}
                  disabled={streaming}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask about this code"
                  aria-label="Message the assistant"
                />
                <button type="submit" disabled={streaming || !draft.trim()}>
                  Send
                </button>
              </form>
            </div>
          </aside>
        </main>
      )}

      {stage === "report" && score && (
        <main className="wrap cc-report">
          <div className="cc-report-head">
            <p className="label">Report</p>
            <h1 className="h2">{TASK.title}</h1>
            <p className="small">
              Scores are 1 to 4. The reference patch is a hint, not the only correct fix. This is a practice round: it
              isn&apos;t part of an {NAME} assessment score.
            </p>
          </div>
          <section className="cc-scores">
            {LABELS.map(([key, label]) => (
              <article key={key}>
                <div className="cc-score-row">
                  <h2 className="h3">{label}</h2>
                  <p className="cc-score" aria-label={`${score[key]} of 4`}>
                    {score[key]}
                    <span className="muted">/4</span>
                  </p>
                </div>
                <p className="small">{score[`${key}Evidence`]}</p>
              </article>
            ))}
          </section>
          <section className="cc-keys">
            <h2 className="h3">Comprehension keys</h2>
            {TASK.questions.map((question) => (
              <div key={question.id}>
                <Prompt text={question.prompt} />
                <p className="small">{question.answerKey}</p>
              </div>
            ))}
          </section>
          <div className="cc-buttons">
            <button type="button" onClick={again}>
              Practise again
            </button>
            <Link href="/">Back to the site</Link>
          </div>
        </main>
      )}
    </div>
  );
}

/** Question text with `code` spans, as curate.ts writes them. */
function Prompt({ text }: { text: string }) {
  return (
    <span className="cc-prompt">
      {text.split(/(`[^`]+`)/).map((part, i) =>
        part.startsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : part,
      )}
    </span>
  );
}

/** Assistant text with fenced code blocks shown as code. */
function Reply({ text }: { text: string }) {
  return (
    <div className="cc-reply">
      {text.split(/```[^\n]*\n([\s\S]*?)(?:```|$)/).map((part, i) =>
        i % 2 ? <pre key={i}>{part.replace(/\n$/, "")}</pre> : part.trim() && <p key={i}>{part.trim()}</p>,
      )}
    </div>
  );
}

/** A plain textarea editor with a line-number gutter. Tab inserts four spaces. */
function CodeArea({ path, value, onChange }: { path: string; value: string; onChange: (v: string) => void }) {
  const gutter = useRef<HTMLPreElement>(null);
  const lines = value.split("\n").length;
  return (
    <div className="cc-code">
      <pre className="cc-gutter" ref={gutter} aria-hidden>
        {Array.from({ length: lines }, (_, i) => i + 1).join("\n")}
      </pre>
      <textarea
        aria-label={`Editing ${path}`}
        value={value}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        wrap="off"
        onChange={(e) => onChange(e.target.value)}
        onScroll={(e) => {
          if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop;
        }}
        onKeyDown={(e) => {
          if (e.key !== "Tab" || e.shiftKey) return;
          e.preventDefault();
          const el = e.currentTarget;
          const { selectionStart: s, selectionEnd: end } = el;
          onChange(`${value.slice(0, s)}    ${value.slice(end)}`);
          requestAnimationFrame(() => el.setSelectionRange(s + 4, s + 4));
        }}
      />
    </div>
  );
}
