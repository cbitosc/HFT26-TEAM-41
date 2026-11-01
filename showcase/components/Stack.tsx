"use client";

import { Reveal, Item } from "./Reveal";
import { Label, Words } from "./fx";
import { NAME } from "@/lib/site";

// Architecture drawn as a temple: four columns that never touch (each part only talks
// to its neighbours through one boundary), standing on the database. The open-source
// work we build on comes from ATTRIBUTIONS.md: used dependencies only.
const COLUMNS: { name: string; parts: string; note: string }[] = [
  { name: "Browser", parts: "Next.js, React, Monaco (bundled)", note: "IDE, report. Calls /api through a same-origin rewrite." },
  { name: "API", parts: "FastAPI, Pydantic v2, SQLAlchemy, Alembic", note: "Sessions, files, events, scoring. Schemas in contracts/ are the source of truth." },
  { name: "Queue", parts: "Celery, Redis", note: "Run, submit, auto-submit every 30 s. Redis also caches every LLM response." },
  { name: "Sandbox", parts: "Docker, python:3.11, node:20, pytest, Jest", note: "Fresh container per run. Network off, non-root, limits on CPU, memory, PIDs, time." },
];

const OSS: [string, string][] = [
  ["LibCST", "bug mutation, feature removal, perf regressions"],
  ["Instructor + OpenAI SDK", "structured output from Featherless"],
  ["Monaco Editor", "the candidate's editor"],
  ["pytest, pytest-json-report, Hypothesis", "tests inside the sandbox"],
  ["mutmut", "optional mutation score in the gate"],
  ["Jest", "JavaScript tests"],
  ["Playwright", "make e2e in headless Chromium"],
  ["JSON Resume", "the portfolio schema we extend"],
  ["LeetCodeDataset", "the DSA bank's 100 imported problems"],
  ["SWE-smith (method)", "the idea behind the mutation filter"],
  ["DeepSeek-V4-Flash, Qwen3-Coder, Qwen2.5-7B", "models via Featherless"],
  ["Lenis, Motion, Fontsource", "this page"],
];

export default function Stack() {
  return (
    <section className="section stack" id="stack">
      <div className="wrap">
        <div className="grid">
          <div className="stack-intro">
            <Label n={8}>The temple</Label>
            <Words className="h2" text="Boring parts, *strict* boundaries." />
            <p>
              Candidate code never runs in the API process. Reference solutions and hidden tests never leave the backend.
              Every model call goes through one module, <code>backend/llm</code>, with a token cap, a low temperature,
              a cache and a hard spend limit.
            </p>
          </div>
        </div>

        <div className="temple">
          <div className="temple-roof" aria-hidden>
            <svg viewBox="0 0 1000 120" preserveAspectRatio="none">
              <path d="M10 118 L500 6 L990 118 Z" />
              <path d="M70 112 L500 22 L930 112 Z" className="inner" />
            </svg>
            <span className="temple-name inscr">{NAME}</span>
          </div>
          <div className="temple-beam" aria-hidden>
            <div className="meander" />
          </div>
          <Reveal as="ol" className="temple-cols" amount={0.15}>
            {COLUMNS.map((c) => (
              <Item as="li" key={c.name} className="tcol">
                <span className="tcol-cap" aria-hidden />
                <div className="tcol-shaft">
                  <h3 className="h3">{c.name}</h3>
                  <p className="tcol-parts">{c.parts}</p>
                  <p className="small">{c.note}</p>
                </div>
              </Item>
            ))}
          </Reveal>
          <div className="temple-base">
            <span className="temple-step" aria-hidden />
            <div className="temple-store">
              <h3 className="h3">Store: PostgreSQL 16</h3>
              <p className="small">Everything stands on it. Events are append-only, enforced by a trigger.</p>
            </div>
            <span className="temple-step s2" aria-hidden />
          </div>
          <p className="small flow-side">
            Beside the temple, the oracle: <b>Featherless</b> serves the generator, assistant, probe and interviewer model
            slots, and the interviewer&apos;s voice from P4.9.
          </p>
        </div>

        <div className="grid oss">
          <h3 className="h3 oss-title">Built on</h3>
          <ul className="oss-list">
            {OSS.map(([name, use]) => (
              <li key={name}>
                <span>{name}</span>
                <span className="small">{use}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
