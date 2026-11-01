"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import { API_BASE, api, ApiError, type SessionOut } from "@/lib/api";
import { Telemetry } from "@/lib/telemetry";
import type { CandidateTaskView } from "@/lib/types";
import { allFiles, editableOnly, isEditable, protectedReason } from "@/lib/workspace";
import AssistantPanel, { type HintMessage } from "./AssistantPanel";
import CodeEditor from "./CodeEditor";
import FileTree from "./FileTree";
import TestResults, { type TaskRunState } from "./TestResults";

const AUTOSAVE_MS = 5000;
const RESYNC_MS = 30_000;
const POLL_MS = 1000;
const FINAL_SAVE_MS = 3000; // save once more this long before the deadline

type Phase = "loading" | "error" | "active" | "submitting" | "submitted" | "timeup";
type SaveState = "saved" | "saving" | "unsaved" | "error";
type OpenFiles = { files: string[]; active: string };

function firstFile(task: CandidateTaskView): string {
  const files = Object.keys(allFiles(task));
  const entry = task.entry_symbols[0]?.split("::")[0];
  if (entry && files.includes(entry)) return entry;
  return files.find((p) => isEditable(task, p)) ?? files[0];
}

function formatRemaining(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail as { message?: string; paths?: Record<string, string> } | string;
    if (typeof d === "string") return d;
    if (d?.paths) return `${d.message}: ${Object.entries(d.paths).map(([p, r]) => `${p} (${r})`).join(", ")}`;
    return err.message;
  }
  return "could not reach the server";
}

export default function SessionIDE({ sessionId }: { sessionId: string }) {
  const telemetry = useMemo(() => new Telemetry(sessionId), [sessionId]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [loadError, setLoadError] = useState("");
  const [tasks, setTasks] = useState<CandidateTaskView[]>([]);
  const [activeTaskId, setActiveTaskId] = useState("");
  const [leftTab, setLeftTab] = useState<"statement" | "tour">("statement");
  const [open, setOpen] = useState<Record<string, OpenFiles>>({});
  const [deadline, setDeadline] = useState(0);
  const [remaining, setRemaining] = useState(0);
  // Content of each file when the session loaded; Monaco keeps later edits in its models.
  const [initialFiles, setInitialFiles] = useState<Record<string, Record<string, string>>>({});
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [runs, setRuns] = useState<Record<string, TaskRunState>>({});
  const [job, setJob] = useState<{ id: string; taskId: string } | null>(null);
  const [runStarting, setRunStarting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [tier, setTier] = useState<SessionOut["tier"]>("novice");
  const [hintMessages, setHintMessages] = useState<Record<string, HintMessage[]>>({});
  const [finishedRuns, setFinishedRuns] = useState<Record<string, number>>({});
  const [serverOffset, setServerOffset] = useState(0);

  // Latest values for timers and async callbacks.
  const tasksRef = useRef<CandidateTaskView[]>([]);
  const files = useRef<Record<string, Record<string, string>>>({}); // taskId -> editable files
  const versions = useRef<Record<string, number>>({}); // edits per task
  const savedVersions = useRef<Record<string, number>>({}); // last version the server has
  const saveChain = useRef<Promise<boolean>>(Promise.resolve(true));
  const offset = useRef(0); // server clock - browser clock
  const finalSaveDone = useRef(false);

  const isDirty = (taskId: string) => (versions.current[taskId] ?? 0) > (savedVersions.current[taskId] ?? 0);

  const applySession = useCallback((s: SessionOut) => {
    offset.current = Date.parse(s.server_time) - Date.now();
    setServerOffset(offset.current);
    setTier(s.tier);
    setDeadline(Date.parse(s.deadline_at));
    setRemaining(Date.parse(s.deadline_at) - Date.parse(s.server_time));
    if (s.status === "submitted") setPhase((p) => (p === "timeup" ? p : "submitted"));
    else if (s.status === "expired") setPhase("timeup");
  }, []);

  const resync = useCallback(async () => {
    try {
      applySession(await api.getSession(sessionId));
    } catch {
      // Keep the last known deadline; the next resync tries again.
    }
  }, [sessionId, applySession]);

  // A write failed: 409 means the session is locked (deadline or submitted elsewhere).
  const handleWriteError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) void resync();
      else setNotice(`Save failed: ${errorText(err)}`);
    },
    [resync],
  );

  const saveDirty = useCallback((): Promise<boolean> => {
    const doSave = async () => {
      const dirty = tasksRef.current.filter((t) => isDirty(t.task_id));
      if (dirty.length === 0) return true;
      setSaveState("saving");
      let ok = true;
      for (const task of dirty) {
        const version = versions.current[task.task_id];
        try {
          await api.saveFiles(sessionId, task.task_id, editableOnly(task, files.current[task.task_id]));
          savedVersions.current[task.task_id] = Math.max(savedVersions.current[task.task_id] ?? 0, version);
        } catch (err) {
          ok = false;
          handleWriteError(err);
        }
      }
      if (ok) setLastSaved(new Date());
      setSaveState(!ok ? "error" : tasksRef.current.some((t) => isDirty(t.task_id)) ? "unsaved" : "saved");
      return ok;
    };
    // Serialize saves so two never race for the same task.
    saveChain.current = saveChain.current.then(doSave, doSave);
    return saveChain.current;
  }, [sessionId, handleWriteError]);

  // Load the session and its tasks.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await api.getSession(sessionId);
        const refs = [...s.tasks].sort((a, b) => a.order - b.order);
        const [views, saved] = await Promise.all([
          Promise.all(refs.map((t) => api.getTask(sessionId, t.task_id))),
          Promise.all(refs.map((t) => api.getFiles(sessionId, t.task_id))),
        ]);
        if (cancelled) return;
        views.forEach((task, i) => {
          // The latest saved snapshot wins; starter files fill in anything it lacks.
          files.current[task.task_id] = { ...editableOnly(task, task.starter_files), ...(saved[i].files ?? {}) };
          versions.current[task.task_id] = 0;
          savedVersions.current[task.task_id] = 0;
        });
        tasksRef.current = views;
        setTasks(views);
        setInitialFiles(Object.fromEntries(views.map((t) => [t.task_id, { ...allFiles(t), ...files.current[t.task_id] }])));
        setActiveTaskId(views[0]?.task_id ?? "");
        setOpen(Object.fromEntries(views.map((t) => [t.task_id, { files: [firstFile(t)], active: firstFile(t) }])));
        setSaveState("saved");
        setPhase("active");
        applySession(s);
      } catch (err) {
        if (cancelled) return;
        setLoadError(err instanceof ApiError && err.status === 404 ? "This session does not exist." : errorText(err));
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, applySession]);

  // Telemetry, autosave and deadline resync run only while the candidate can edit.
  useEffect(() => {
    if (phase !== "active") return;
    telemetry.start();
    const autosave = setInterval(() => void saveDirty(), AUTOSAVE_MS);
    const resyncTimer = setInterval(() => void resync(), RESYNC_MS);
    // Closing or reloading the tab: send unsaved edits (up to 5 s of work) with keepalive.
    // Best effort; browsers cap keepalive bodies at 64 KB.
    const onPageHide = () => {
      for (const task of tasksRef.current.filter((t) => isDirty(t.task_id))) {
        void fetch(`${API_BASE}/sessions/${sessionId}/tasks/${task.task_id}/files`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ files: editableOnly(task, files.current[task.task_id]) }),
          keepalive: true,
        }).catch(() => {});
      }
    };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      clearInterval(autosave);
      clearInterval(resyncTimer);
      window.removeEventListener("pagehide", onPageHide);
      telemetry.stop();
    };
  }, [phase, sessionId, telemetry, saveDirty, resync]);

  // Countdown; at the deadline the editor locks (the backend auto-submits within 30 s).
  useEffect(() => {
    if (phase !== "active" || !deadline) return;
    const tick = setInterval(() => {
      const left = deadline - (Date.now() + offset.current);
      setRemaining(left);
      if (left <= FINAL_SAVE_MS && !finalSaveDone.current) {
        finalSaveDone.current = true;
        void saveDirty();
      }
      if (left <= 0) setPhase("timeup");
    }, 1000);
    return () => clearInterval(tick);
  }, [phase, deadline, saveDirty]);

  // Poll the run job; show visible results as soon as they exist.
  useEffect(() => {
    if (!job) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const view = await api.getJob(job.id);
        if (stopped) return;
        const finished = view.status === "done" || view.status === "failed";
        setRuns((r) => ({
          ...r,
          [job.taskId]: {
            running: !finished,
            result: view.result,
            error: view.status === "failed" && !view.result ? (view.error ?? "the run failed") : null,
          },
        }));
        if (finished) {
          setFinishedRuns((n) => ({ ...n, [job.taskId]: (n[job.taskId] ?? 0) + 1 }));
          setJob(null);
          return;
        }
      } catch (err) {
        if (stopped) return;
        if (err instanceof ApiError && err.status === 404) {
          setRuns((r) => ({ ...r, [job.taskId]: { running: false, result: null, error: "the run expired" } }));
          setJob(null);
          return;
        }
      }
      timer = setTimeout(poll, POLL_MS);
    };
    timer = setTimeout(poll, POLL_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [job]);

  const activeTask = tasks.find((t) => t.task_id === activeTaskId);
  const locked = phase !== "active";
  const hasAssistant = tier === "adept" || tier === "master";

  const updateHints = useCallback(
    (taskId: string, update: (prev: HintMessage[]) => HintMessage[]) =>
      setHintMessages((m) => ({ ...m, [taskId]: update(m[taskId] ?? []) })),
    [],
  );

  const onEdit = (task: CandidateTaskView, path: string, value: string) => {
    if (locked || !isEditable(task, path)) return;
    files.current[task.task_id][path] = value;
    versions.current[task.task_id] = (versions.current[task.task_id] ?? 0) + 1;
    setSaveState("unsaved");
  };

  const openFile = (taskId: string, path: string) =>
    setOpen((o) => {
      const cur = o[taskId];
      return { ...o, [taskId]: { files: cur.files.includes(path) ? cur.files : [...cur.files, path], active: path } };
    });

  const closeFile = (taskId: string, path: string) =>
    setOpen((o) => {
      const cur = o[taskId];
      const remainingFiles = cur.files.filter((p) => p !== path);
      if (remainingFiles.length === 0) return o; // keep one tab open
      const active = cur.active === path ? remainingFiles[remainingFiles.length - 1] : cur.active;
      return { ...o, [taskId]: { files: remainingFiles, active } };
    });

  const run = async () => {
    if (!activeTask || locked || job || runStarting) return;
    const taskId = activeTask.task_id;
    const version = versions.current[taskId] ?? 0;
    const previous = runs[taskId];
    setNotice(null);
    setRunStarting(true);
    setRuns((r) => ({ ...r, [taskId]: { running: true, result: null, error: null } }));
    try {
      const { job_id } = await api.run(sessionId, taskId, editableOnly(activeTask, files.current[taskId]));
      // The run stored a snapshot of this task; autosave the other tasks too.
      savedVersions.current[taskId] = Math.max(savedVersions.current[taskId] ?? 0, version);
      setJob({ id: job_id, taskId });
      void saveDirty();
    } catch (err) {
      setRuns((r) => ({ ...r, [taskId]: previous ?? { running: false, result: null, error: null } }));
      if (err instanceof ApiError && err.status === 429) {
        setNotice("A run is already in progress for this session. Try again when it finishes.");
      } else {
        handleWriteError(err);
      }
    } finally {
      setRunStarting(false);
    }
  };

  const submit = async () => {
    setConfirming(false);
    setPhase("submitting");
    await saveDirty();
    try {
      await api.submit(sessionId);
      setPhase("submitted");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        await resync();
      } else {
        setPhase("active");
        setNotice(`Submit failed: ${errorText(err)}`);
      }
    }
  };

  if (phase === "loading") return <p className="p-8 text-gray-500">Loading session…</p>;
  if (phase === "error") return <p className="p-8 text-red-700">Could not load the session: {loadError}</p>;
  if (phase === "submitted") {
    return (
      <main className="flex h-screen items-center justify-center bg-gray-50">
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center shadow-sm">
          <h1 className="mb-2 text-xl font-semibold">Submitted</h1>
          <p className="text-gray-600">Your solutions are being graded. You can close this tab.</p>
          <p className="mt-4 text-sm text-gray-600">
            If your recruiter set up an AI interview,{" "}
            <a href={`/interview/${sessionId}`} className="text-blue-700 underline">
              start it here
            </a>
            . It never changes your score.
          </p>
        </div>
      </main>
    );
  }
  if (!activeTask) return <p className="p-8 text-gray-500">This session has no tasks.</p>;

  const taskFiles = allFiles(activeTask);
  const openState = open[activeTask.task_id];
  const activePath = openState.active;
  const activeEditable = isEditable(activeTask, activePath);
  const runBusy = job !== null || runStarting;
  const saveText = {
    saved: lastSaved ? `Saved ${lastSaved.toLocaleTimeString()}` : "All changes saved",
    saving: "Saving…",
    unsaved: "Unsaved changes",
    error: "Save failed, retrying",
  }[saveState];

  return (
    <div className="flex h-screen flex-col bg-white text-gray-900">
      <header className="flex h-12 shrink-0 items-center gap-4 border-b border-gray-200 px-4">
        <span className="font-semibold">Assessment</span>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs uppercase text-gray-600">{tier}</span>
        <span className={`font-mono text-lg ${remaining < 5 * 60_000 ? "text-red-700" : ""}`} title="Time remaining">
          {formatRemaining(remaining)}
        </span>
        <span className={`text-sm ${saveState === "error" ? "text-red-700" : "text-gray-500"}`}>{saveText}</span>
        <div className="ml-auto flex gap-2">
          <button
            onClick={run}
            disabled={locked || runBusy}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {runBusy ? "Running…" : "Run"}
          </button>
          <button
            onClick={() => setConfirming(true)}
            disabled={locked}
            className="rounded border border-gray-300 px-4 py-1.5 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      </header>

      {phase === "timeup" && (
        <div className="bg-red-600 px-4 py-2 text-center font-medium text-white">Time&apos;s up — submitted.</div>
      )}
      {notice && (
        <div className="flex items-center bg-amber-100 px-4 py-1.5 text-sm text-amber-900">
          {notice}
          <button onClick={() => setNotice(null)} className="ml-auto px-2" aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[26rem] shrink-0 flex-col border-r border-gray-200">
          <nav className="flex border-b border-gray-200">
            {tasks.map((t, i) => (
              <button
                key={t.task_id}
                onClick={() => setActiveTaskId(t.task_id)}
                className={`flex-1 px-3 py-2 text-sm ${t.task_id === activeTaskId ? "border-b-2 border-blue-600 font-semibold" : "text-gray-600"}`}
              >
                {i + 1}. {t.kind === "dsa" ? "DSA" : "Domain"} task
              </button>
            ))}
          </nav>
          {activeTask.repo_tour_md && (
            <nav className="flex gap-3 border-b border-gray-200 px-4 text-sm">
              {(["statement", "tour"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setLeftTab(tab)}
                  className={`py-1.5 ${leftTab === tab ? "font-semibold text-blue-700" : "text-gray-600"}`}
                >
                  {tab === "statement" ? "Statement" : "Repo tour"}
                </button>
              ))}
            </nav>
          )}
          <div className="markdown min-h-0 flex-1 overflow-auto p-4 text-sm">
            {leftTab === "tour" && activeTask.repo_tour_md ? (
              <Markdown>{activeTask.repo_tour_md}</Markdown>
            ) : (
              <>
                <Markdown>{activeTask.statement_md}</Markdown>
                {activeTask.perf && <p>Time budget: {activeTask.perf.budget_ms} ms.</p>}
                {activeTask.dsa_cases && activeTask.dsa_cases.visible.length > 0 && (
                  <>
                    <h3>Examples</h3>
                    {activeTask.dsa_cases.visible.map((c) => (
                      <pre key={c.id}>
                        {`input:    ${JSON.stringify(c.input)}\nexpected: ${JSON.stringify(c.expected)}`}
                      </pre>
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1">
            <div className="w-56 shrink-0 overflow-auto border-r border-gray-200 py-2 text-sm">
              <FileTree
                paths={Object.keys(taskFiles)}
                active={activePath}
                readOnlyReason={(p) => (isEditable(activeTask, p) ? null : (protectedReason(p) ?? "read-only"))}
                onOpen={(p) => openFile(activeTask.task_id, p)}
              />
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="flex shrink-0 overflow-x-auto border-b border-gray-200 bg-gray-50 text-sm">
                {openState.files.map((p) => (
                  <div
                    key={p}
                    className={`flex items-center gap-1 border-r border-gray-200 px-3 py-1.5 ${p === activePath ? "bg-white font-medium" : "text-gray-600"}`}
                  >
                    <button onClick={() => openFile(activeTask.task_id, p)} className="whitespace-nowrap">
                      {p.split("/").pop()}
                      {!isEditable(activeTask, p) && <span className="ml-1 text-xs text-gray-400">read-only</span>}
                    </button>
                    {openState.files.length > 1 && (
                      <button onClick={() => closeFile(activeTask.task_id, p)} className="px-1 text-gray-400 hover:text-gray-700" aria-label={`Close ${p}`}>
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <div className="min-h-0 flex-1">
                <CodeEditor
                  taskId={activeTask.task_id}
                  path={activePath}
                  initialValue={initialFiles[activeTask.task_id]?.[activePath] ?? ""}
                  readOnly={locked || !activeEditable}
                  telemetry={telemetry}
                  onChange={(value) => onEdit(activeTask, activePath, value)}
                />
              </div>
            </div>
          </div>
          <div className="h-64 shrink-0 border-t border-gray-200">
            <div className="border-b border-gray-200 bg-gray-50 px-3 py-1 text-xs font-semibold uppercase text-gray-500">
              Test results
            </div>
            <div className="h-[calc(100%-1.75rem)]">
              <TestResults state={runs[activeTask.task_id]} />
            </div>
          </div>
        </section>

        {hasAssistant && (
          <aside className="w-80 shrink-0 border-l border-gray-200">
            <AssistantPanel
              key={activeTask.task_id}
              sessionId={sessionId}
              taskId={activeTask.task_id}
              messages={hintMessages[activeTask.task_id] ?? []}
              onMessages={updateHints}
              serverOffset={serverOffset}
              locked={locked}
              runCount={finishedRuns[activeTask.task_id] ?? 0}
            />
          </aside>
        )}
      </div>

      {confirming && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30">
          <div className="w-96 rounded-lg bg-white p-6 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">Submit your assessment?</h2>
            <p className="mb-4 text-sm text-gray-600">
              All tasks are submitted together and graded. You can&apos;t edit after submitting.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirming(false)} className="rounded border border-gray-300 px-4 py-1.5 text-sm">
                Cancel
              </button>
              <button onClick={submit} className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white">
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
