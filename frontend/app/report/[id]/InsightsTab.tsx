"use client";

// Report details for the recruiter (F3): AI summary, certificate per task, claim
// verification map, hidden-test timeline, integrity notes and the AI efficiency breakdown.
// Only the Score tab is the score; integrity notes and the summary are labelled "not scored".
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, type ReportDetails, type Verdict } from "@/lib/api";
import { KeyForm, readKey, saveKey } from "./RecruiterKey";

const VERDICT: Record<Verdict, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  verified: { label: "Verified", variant: "success" },
  partly: { label: "Partly", variant: "warning" },
  not_verified: { label: "Not verified", variant: "destructive" },
  not_tested: { label: "Not tested", variant: "secondary" },
};

const CERT_FIELDS: [string, string][] = [
  ["reference_pass", "Reference passes"],
  ["starter_fail", "Starter fails"],
  ["mutation_score", "Mutation score"],
  ["stub_fail_rate", "Trivial stubs fail"],
  ["bruteforce_agree", "Brute force agrees"],
  ["budget_ms", "Perf budget (ms)"],
  ["perf_ref_ms", "Reference perf (ms)"],
  ["changed_lines", "Lines in the fix"],
];

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value <= 1 && !Number.isInteger(value) ? `${Math.round(value * 100)}%` : String(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function pct(value: number | null): string {
  return value === null ? "n/a" : `${Math.round(value * 100)}%`;
}

function NotScored() {
  return <Badge variant="outline">not scored</Badge>;
}

function Summary({ sessionId, recruiterKey }: { sessionId: string; recruiterKey: string }) {
  const [state, setState] = useState<{ text: string; label: string } | "loading" | "unavailable">("loading");
  useEffect(() => {
    let cancelled = false;
    api
      .getSummary(sessionId, recruiterKey)
      .then((out) => !cancelled && setState({ text: out.summary, label: out.label }))
      .catch(() => !cancelled && setState("unavailable"));
    return () => {
      cancelled = true;
    };
  }, [sessionId, recruiterKey]);
  return (
    <Card data-testid="ai-summary">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Summary</CardTitle>
        <Badge variant="outline">AI summary, not scored</Badge>
      </CardHeader>
      <CardContent className="text-sm leading-6 text-gray-800">
        {state === "loading" && <span className="text-gray-500">Writing the summary…</span>}
        {state === "unavailable" && <span className="text-gray-500">The summary is unavailable right now.</span>}
        {typeof state === "object" && state.text}
        <p className="mt-2 text-xs text-gray-500">Written by a model from the numbers on this page only.</p>
      </CardContent>
    </Card>
  );
}

function Certificates({ details }: { details: ReportDetails }) {
  return (
    <section className="grid gap-4 md:grid-cols-2" data-testid="certificates">
      {details.certificates.map((c, i) => (
        <Card key={c.task_id}>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle>
                {i + 1}. {c.kind === "dsa" ? "DSA" : "Domain"} task certificate
              </CardTitle>
              <Badge variant={c.certified ? "success" : "secondary"}>{c.certified ? "Gate passed" : "Not gated"}</Badge>
            </div>
            <CardDescription>{c.task_id}</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {CERT_FIELDS.filter(([key]) => c.fields[key] !== null && c.fields[key] !== undefined).map(([key, label]) => (
                <div key={key} className="contents">
                  <dt className="text-gray-500">{label}</dt>
                  <dd className="tabular-nums">{show(c.fields[key])}</dd>
                </div>
              ))}
              <dt className="text-gray-500">Files in scope</dt>
              <dd className="break-all">{(c.fields.scope_files as string[] | undefined)?.join(", ") || "—"}</dd>
            </dl>
          </CardContent>
        </Card>
      ))}
    </section>
  );
}

function Claims({ details }: { details: ReportDetails }) {
  const kind = { concept: "Concept", dsa_topic: "DSA topic", runtime: "Language" };
  return (
    <Card data-testid="claims">
      <CardHeader>
        <CardTitle>Claim verification</CardTitle>
        <CardDescription>
          What the portfolio claims, which task tested it, and how that task went (Verified ≥ 80, Partly ≥ 45).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-gray-500">
            <tr>
              <th className="pb-2 pr-3 font-semibold">Claim</th>
              <th className="pb-2 pr-3 font-semibold">Evidence</th>
              <th className="pb-2 pr-3 font-semibold">Tested by</th>
              <th className="pb-2 font-semibold">Result</th>
            </tr>
          </thead>
          <tbody>
            {details.claims.map((c) => (
              <tr key={`${c.kind}:${c.claim}`} className="border-t border-gray-100">
                <td className="py-2 pr-3">
                  <div className="font-medium">{c.claim}</div>
                  <div className="text-xs text-gray-500">{kind[c.kind]}</div>
                </td>
                <td className="py-2 pr-3 text-gray-600">{c.evidence}</td>
                <td className="py-2 pr-3 text-xs text-gray-600">{c.tested_by.join(", ") || "—"}</td>
                <td className="py-2">
                  <Badge variant={VERDICT[c.verdict].variant}>{VERDICT[c.verdict].label}</Badge>
                  {c.correctness !== null && <span className="ml-2 tabular-nums text-gray-600">{c.correctness.toFixed(0)}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function Timeline({ details }: { details: ReportDetails }) {
  return (
    <Card data-testid="timeline">
      <CardHeader>
        <CardTitle>Hidden-test progress</CardTitle>
        <CardDescription>
          Share of hidden tests passing at each Run (dots) and at Submit; orange lines are hints. Candidates never see
          the hidden results.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        {details.timelines.map((line, i) => {
          const data = line.points.map((p) => ({
            minute: p.minute,
            hidden: p.hidden_rate === null ? null : Math.round(p.hidden_rate * 100),
            visible: p.visible_rate === null ? null : Math.round(p.visible_rate * 100),
            kind: p.kind,
          }));
          return (
            <div key={line.task_id}>
              <div className="mb-2 text-sm font-medium">
                {i + 1}. {line.task_id}
              </div>
              {data.length === 0 ? (
                <p className="text-sm text-gray-500">No runs.</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={data} margin={{ top: 10, right: 16, bottom: 4, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="minute" type="number" domain={[0, "dataMax"]} unit=" min" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(value, name) => [`${value}%`, name === "hidden" ? "Hidden" : "Visible"]} />
                    <Legend formatter={(name) => (name === "hidden" ? "Hidden tests" : "Visible tests")} />
                    {line.hints.map((h) => (
                      <ReferenceLine
                        key={h.ts}
                        x={h.minute}
                        stroke="#ea580c"
                        strokeDasharray="4 3"
                        label={{ value: `L${h.level}`, fontSize: 10, fill: "#ea580c", position: "top" }}
                      />
                    ))}
                    <Line type="stepAfter" dataKey="hidden" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                    <Line type="stepAfter" dataKey="visible" stroke="#9ca3af" strokeWidth={1.5} dot={{ r: 2 }} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function Integrity({ details }: { details: ReportDetails }) {
  const n = details.integrity;
  const large = n.pastes.filter((p) => p.large);
  const afterHint = n.pastes.filter((p) => p.after_hint);
  return (
    <Card data-testid="integrity">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Integrity notes</CardTitle>
        <NotScored />
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(
            [
              ["Pastes", `${n.pastes.length} (${n.paste_chars} chars)`],
              ["Large pastes", String(large.length)],
              ["Pastes soon after a hint", String(afterHint.length)],
              ["Tab switches", String(n.blurs)],
            ] as [string, string][]
          ).map(([label, value]) => (
            <div key={label} className="rounded-lg border border-gray-200 p-3">
              <div className="text-xs text-gray-500">{label}</div>
              <div className="mt-1 font-semibold tabular-nums">{value}</div>
            </div>
          ))}
        </div>
        {n.flags.length > 0 && (
          <div>
            <div className="font-medium">Code flags</div>
            <ul className="mt-1 list-disc pl-5 text-gray-700">
              {n.flags.map((f) => (
                <li key={`${f.task_id}:${f.path}:${f.line}:${f.rule}`}>
                  {f.path}:{f.line} ({f.rule}) <code className="text-xs">{f.excerpt}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
        {n.refused_writes.length > 0 && <p>Writes to protected files were refused: {n.refused_writes.join(", ")}.</p>}
        {n.extraction_attempts > 0 && <p>Asked the assistant for the solution {n.extraction_attempts} time(s); refused.</p>}
        <p className="text-xs text-gray-500">
          Large paste: 300+ characters. A paste within 2 minutes of a hint may be hint code. None of this changes the
          score; read it with the timeline and the Trail Map.
        </p>
      </CardContent>
    </Card>
  );
}

function Efficiency({ details }: { details: ReportDetails }) {
  const e = details.efficiency;
  if (!e) {
    return (
      <Card data-testid="efficiency">
        <CardHeader>
          <CardTitle>AI efficiency</CardTitle>
          <CardDescription>Novice assessments have no assistant, so there is no AI efficiency.</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  const data = e.parts.map((p) => ({ name: p.name, value: p.value === null ? 0 : Math.round(p.value * 100) }));
  return (
    <Card data-testid="efficiency">
      <CardHeader>
        <CardTitle>AI efficiency {pct(e.value)}</CardTitle>
        <CardDescription>
          {e.hints} hint(s), {e.extraction_attempts} extraction attempt(s) (−15 points each). Scaled by{" "}
          {e.scale.toFixed(2)} for correctness. Counts for 20 of the 100 points.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} layout="vertical" margin={{ left: 40, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={110} />
            <Tooltip formatter={(value) => [`${value}%`, "Score"]} />
            <Bar dataKey="value" fill="#2563eb" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
        <div className="space-y-3 text-sm">
          {e.parts.map((p) => (
            <div key={p.name} className="border-b border-gray-100 pb-2">
              <div className="flex items-baseline justify-between">
                <span className="font-medium">{p.name}</span>
                <span className="tabular-nums">
                  {pct(p.value)} <span className="text-xs text-gray-500">× {p.weight}</span>
                </span>
              </div>
              <p className="text-gray-600">{p.evidence}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function InsightsTab({ sessionId }: { sessionId: string }) {
  const [key, setKey] = useState(readKey);
  const [details, setDetails] = useState<ReportDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    api
      .getReport(sessionId, key)
      .then((out) => {
        if (!cancelled) {
          setDetails(out);
          setError(null);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          saveKey("");
          setKey("");
          setError("That recruiter key was not accepted.");
        } else if (err instanceof ApiError && err.status === 503) {
          setError("The server has no RECRUITER_API_KEY set.");
        } else {
          setError("Could not load the report details.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, key]);

  if (!key) {
    return (
      <KeyForm
        error={error}
        onKey={(next) => {
          setError(null);
          setKey(next);
        }}
      />
    );
  }
  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!details) return <p className="text-sm text-gray-500">Loading the report details…</p>;
  return (
    <div className="space-y-6" data-testid="insights">
      <Summary sessionId={sessionId} recruiterKey={key} />
      <Certificates details={details} />
      <Claims details={details} />
      <Timeline details={details} />
      <Efficiency details={details} />
      <Integrity details={details} />
    </div>
  );
}
