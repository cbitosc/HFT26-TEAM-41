"use client";

// Interview tab (F5, recruiter key): set up the AI voice interview for this submitted
// session (company, role, job description), then its transcript and the "x of y
// submission facts mentioned" check. Report only: never part of the score.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type InterviewReport, type InterviewSetup } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KeyForm, readKey, saveKey } from "./RecruiterKey";

const BLOCK: Record<string, string> = { role: "Role", portfolio: "Portfolio", submission: "Submission" };
const EMPTY: InterviewSetup = { company: "", role: "", job_description: "", focus: "" };

function SetupForm({ sessionId, recruiterKey, onDone }: { sessionId: string; recruiterKey: string; onDone: () => void }) {
  const [setup, setSetup] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const field = "w-full rounded border border-gray-300 px-2 py-1.5 text-sm";
  return (
    <form
      className="flex max-w-xl flex-col gap-3"
      data-testid="interview-setup"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await api.setUpInterview(sessionId, setup, recruiterKey);
          onDone();
        } catch (err) {
          setError(err instanceof ApiError ? String(err.message) : "Could not set up the interview.");
        } finally {
          setBusy(false);
        }
      }}
    >
      <p className="text-sm text-gray-600">
        No interview yet. The AI interviewer uses only what you enter here about the company. One model call writes
        five questions: two about the role, one about a portfolio project, two about the candidate&apos;s submitted
        code.
      </p>
      <label className="text-sm">
        Company
        <input className={field} required maxLength={120} value={setup.company} onChange={(e) => setSetup({ ...setup, company: e.target.value })} />
      </label>
      <label className="text-sm">
        Role
        <input className={field} required maxLength={120} value={setup.role} onChange={(e) => setSetup({ ...setup, role: e.target.value })} />
      </label>
      <label className="text-sm">
        Job description (optional)
        <textarea className={field} rows={4} maxLength={6000} value={setup.job_description} onChange={(e) => setSetup({ ...setup, job_description: e.target.value })} />
      </label>
      <label className="text-sm">
        Focus competencies (optional)
        <input className={field} maxLength={600} value={setup.focus} onChange={(e) => setSetup({ ...setup, focus: e.target.value })} />
      </label>
      <button disabled={busy} className="self-start rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50">
        {busy ? "Writing questions…" : "Set up interview"}
      </button>
      {error && <p className="text-sm text-red-700">{error}</p>}
    </form>
  );
}

function Report({ sessionId, rep }: { sessionId: string; rep: InterviewReport }) {
  const qText = Object.fromEntries(rep.questions.map((q) => [q.id, q]));
  const link = `/interview/${sessionId}`;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Badge variant="outline">{rep.label}</Badge>
        <span>
          {rep.setup.role} at {rep.setup.company}
        </span>
        <span className="text-gray-500">Status: {rep.status}</span>
        <span className="text-gray-500">
          Candidate link: <a className="text-blue-700 underline" href={link}>{link}</a>
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            <span data-testid="interview-facts">
              {rep.facts.mentioned} of {rep.facts.total} submission facts mentioned
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p className="mb-3 text-gray-500">
            Plain-code check of the candidate&apos;s answers against what their own diff changed (keyword and fuzzy
            match). It does not judge accent, fluency or voice, and is not part of the score.
          </p>
          <ul className="flex flex-col gap-2">
            {rep.facts.questions.map((q) => (
              <li key={q.question_id}>
                <div className="text-gray-700">{q.text}</div>
                <div className="mt-1 flex flex-wrap gap-2">
                  {q.facts.length === 0 && <span className="text-gray-400">No code changed on this task.</span>}
                  {q.facts.map((f) => (
                    <Badge key={f.label} variant={f.mentioned ? "success" : "outline"}>
                      {f.mentioned ? "✓" : "✗"} {f.label}
                    </Badge>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transcript</CardTitle>
        </CardHeader>
        <CardContent>
          {rep.transcript.length === 0 && <p className="text-sm text-gray-500">The candidate hasn&apos;t started yet.</p>}
          <ol className="flex flex-col gap-3 text-sm" data-testid="interview-transcript">
            {rep.transcript.map((t, i) => (
              <li key={i} className={t.speaker === "candidate" ? "pl-6" : ""}>
                <div className="text-xs text-gray-500">
                  {t.speaker === "interviewer" ? "Interviewer (AI)" : "Candidate"}
                  {t.question_id && qText[t.question_id] && ` · ${BLOCK[qText[t.question_id].block]}`}
                  {t.speaker === "interviewer" && t.kind === "follow_up" && " · follow-up"}
                  {t.llm_used && " · model reply"}
                </div>
                <p className={t.speaker === "candidate" ? "text-gray-900" : "text-gray-700"}>{t.text}</p>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <p className="text-xs text-gray-500">
        Tokens: plan {rep.tokens.plan}, turns {rep.tokens.turns} of {rep.tokens.budget} ({rep.tokens.llm_calls} model
        replies). Audio is not stored.
      </p>
    </div>
  );
}

export default function InterviewTab({ sessionId }: { sessionId: string }) {
  const [key, setKey] = useState(readKey);
  const [rep, setRep] = useState<InterviewReport | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!key) return;
    api
      .getInterviewReport(sessionId, key)
      .then((out) => {
        setRep(out);
        setMissing(false);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setMissing(true);
        else if (err instanceof ApiError && err.status === 401) {
          saveKey("");
          setKey("");
          setError("That recruiter key was not accepted.");
        } else if (err instanceof ApiError && err.status === 503) setError("The server has no RECRUITER_API_KEY set.");
        else setError("Could not load the interview.");
      });
  }, [sessionId, key]);

  useEffect(load, [load]);

  if (!key) return <KeyForm error={error} onKey={setKey} />;
  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (missing) return <SetupForm sessionId={sessionId} recruiterKey={key} onDone={load} />;
  if (!rep) return <p className="text-sm text-gray-500">Loading interview…</p>;
  return (
    <div>
      <div className="mb-3 text-right">
        <button onClick={load} className="rounded border border-gray-300 px-3 py-1 text-xs hover:bg-gray-50">
          Refresh
        </button>
      </div>
      <Report sessionId={sessionId} rep={rep} />
    </div>
  );
}
