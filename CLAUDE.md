# Portfolio-Driven Assessment Platform (HFT26 Team 41 · JL)

## What we're building
A platform that turns a candidate's JSON portfolio into a validated 60-minute
coding assessment (one domain task + one DSA task) in their own tech stack,
runs it in sandboxes, offers a guarded AI assistant on Adept/Master tiers,
an optional AI voice interviewer, and a deterministic performance report.

Context files (the repo's docs/ folder is the single source of truth; the
shared Claude doc is an older snapshot):
- docs/BLUEPRINT.md — decisions, architecture, scoring, resources, plan
- docs/BUILD_PROMPTS.md — every build prompt, in order
- docs/PROGRESS.md — status table, decisions log, session log
- docs/INTERVIEWER.md — AI voice interviewer spec

## Session protocol (every session)
Start:
1. `git pull` on main.
2. Read this file, then docs/PROGRESS.md, then the relevant parts of
   docs/BLUEPRINT.md and docs/BUILD_PROMPTS.md.
3. Create a branch named after the prompt (e.g. `p1-1-db-api`).
End:
1. Run the prompt's acceptance checks and show the output.
2. Update the item's row in docs/PROGRESS.md and add a session-log row
   (date, who, what was done, next step).
3. Commit with the prompt ID in the message (e.g. "P1.1 db and api").
4. Push the branch to origin.
5. Merge into main only when the checks pass; push main.
6. Report: what changed, how to verify it, known gaps.

## Non-negotiable rules
1. LLMs never decide correctness or scores. Scores come only from test
   results and the formulas in backend/scoring.
2. Reference solutions and hidden tests never leave the backend: not to the
   browser, not into any model's context, not in any API response.
3. Candidate code runs only inside runner containers: network disabled,
   CPU/memory/PID/time limits, non-root user, fresh container per run.
4. The schemas in contracts/ are the source of truth. Changing a schema means:
   update the JSON Schema → `make contracts` → update backend and frontend
   in the same change.
5. Scoring is reproducible: the same events + snapshots give the same score.
6. All Featherless calls (text and speech) go through backend/llm. Never
   call the API elsewhere.
7. Secrets live in .env only. Never commit .env.
8. Trail Map metrics, integrity flags, and the voice interview are shown in
   the report but never affect the score.
9. Hidden tests run only in their own sandbox, never next to visible ones.
   Candidates can edit only starter files outside tests/config
   (app/workspace.py), and a run counts only if exactly the task's expected
   test ids were collected (TaskSpec.visible_test_ids / hidden_test_ids).
   Threat model and known limits: docs/BLUEPRINT.md section 11.

## Token policy (whole project)
- Every Featherless call sets max_tokens and a low temperature.
- Use the smallest model slot that does the job. Prefer plain code over an
  LLM call whenever the result can be computed.
- Cache every LLM and TTS response by input hash in Redis (on by default).
- Never send whole repos; send only the needed files or snippets. Truncate
  test output to the last 40 lines.
- Tests and CI always mock Featherless; they never call the real API.
- Log tokens per call; keep per-assessment and per-interview totals.
- Reuse generated tasks when inputs are identical. Pre-generate demo data once.
- AI solve-rate probe: 3 attempts. Repair loop: at most 2 tries.
- LLM calls are allowed for UX features (assistant, interviewer, resume parsing, report summary) within LLM_BUDGET_USD; scores stay test-only.

## Stack
- Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic,
  Celery + Redis, pytest
- LLM: OpenAI Python SDK with base_url https://api.featherless.ai/v1,
  wrapped with Instructor (JSON mode). Model slots: generator, assistant,
  probe, interviewer.
- Speech: Featherless POST /v1/audio/speech for the interviewer's voice;
  browser Web Speech API for listening. No ElevenLabs or other paid voice
  services anywhere.
- Runner: Docker, runtime images in runtimes/
- Frontend: Next.js (App Router), TypeScript, Tailwind, @monaco-editor/react
- Database: PostgreSQL 16

## Environment variables (keep .env.example in sync)
DATABASE_URL, REDIS_URL, FEATHERLESS_API_KEY,
FEATHERLESS_MODEL_GENERATOR, FEATHERLESS_MODEL_ASSISTANT,
FEATHERLESS_MODEL_PROBE, FEATHERLESS_MODEL_INTERVIEWER,
FEATHERLESS_TTS_MODEL, FEATHERLESS_TTS_VOICE,
INTERVIEW_TOKEN_BUDGET (default 4000), RECRUITER_API_KEY (X-Recruiter-Key header on
recruiter routes; unset: they return 503)

Also used by the P0 code (see .env.example for values and comments):
- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB (postgres container)
- Per slot (GENERATOR, ASSISTANT, PROBE, INTERVIEWER):
  FEATHERLESS_PRICE_IN_<SLOT>, FEATHERLESS_PRICE_OUT_<SLOT> (USD per 1M
  tokens; required, the budget guard fails closed without them) and
  FEATHERLESS_CHAT_TEMPLATE_KWARGS_<SLOT> (JSON, e.g. {"thinking":false})
- LLM_TIMEOUT_S, LLM_MAX_RETRIES, LLM_CACHE_ENABLED, LLM_CACHE_TTL_S,
  LLM_BUDGET_USD (hard spend cap; once reached only cached responses are served)

## Layout
contracts/   JSON Schemas (source of truth) + fixtures + generated types
frontend/    Next.js app: app/practice (LeetCode-style problem list and
             app/practice/[id] editor; lib/practice.ts, no session),
             app/recruiter, app/session/[id] (IDE; AssistantPanel.tsx: assistant-ui
             hint chat, Adept/Master only), app/report/[id]
             (tabs: Score = per-task table, Re-grade; Insights = InsightsTab.tsx: AI
             summary, certificates, claim map, Recharts timeline, efficiency parts,
             integrity notes; Trail Map = TrailTab.tsx, React Flow; recruiter key in
             sessionStorage via RecruiterKey.tsx; Interview = InterviewTab.tsx),
             app/interview/[id] (showcase interview room + OracleOrb, speech.ts TtsPlayer).
             components/ui/ (shadcn/ui Card, Badge, Tabs; lib/utils.ts cn),
             lib/api.ts (browser client, calls /api,
             rewritten to API_URL in next.config.ts), lib/telemetry.ts,
             lib/workspace.ts (mirror of backend/app/workspace.py: keep in sync),
             lib/monaco.ts (bundled Monaco, no CDN; add a language there)
backend/     app/            FastAPI app and plumbing:
                             main.py, routes/ (one module per resource),
                             models.py (SQLAlchemy tables), db.py, jobs.py
                             (enqueue, job status, run lock), celery_app.py
                             (Celery app + beat schedule), worker.py (Celery
                             tasks), grading.py (run/submit/auto-submit),
                             workspace.py (editable allowlist), integrity.py
                             (suspicious-code scan), candidate_view.py, config.py
             builder/        task builders: manual.py (P1.3 demo tasks; its bug comes
                             from mutate.py, hand AST bug as fallback), mutate.py
                             (P2.2 mutation engine, LibCST operators, sandbox
                             pre-filter, draft Novice spec), remove_feature.py
                             (P2.3: stub a concept across 2-3 files, runner
                             checks, draft Adept spec), master.py (P2.4: bug +
                             LibCST perf regression in another file, budget
                             calibrated in the sandbox), perf.py (perf_ms from
                             perf tests; also used by submit), enrich.py (P2.5:
                             one generator call for statement + rename map, leak
                             check, LibCST renaming re-checked in the sandbox),
                             tasks.py (shared:
                             concepts.yaml, starter files, visible/hidden split,
                             validation), seeds.py, seed_demo.py,
                             dsa_bank.py (P2.6: bank loading, select_problem,
                             stubs, statement, renamed-reference check, task
                             build), dsa_rewrite.py (one generator call per
                             problem+domain, validation, template fallback),
                             dsa_demo.py (build one DSA task for a portfolio)
             app/practice.py practice mode: bank problem -> TaskSpec, Run / custom
                             input / Submit through app.dsa; practice_jobs.py
                             (Redis job records, one job and 20 per minute per
                             X-Client-Id); routes/practice.py; Celery practice_job.
                             Serves only practice-only problems; Submit returns
                             pass counts and a status, never cases or output
             app/dsa.py      DSA grading: harness gets inputs only, outputs
                             compared on the backend (runner/harness/:
                             python_cases.py, node_cases.js); hidden_sample()
                             picks a session's ≤30 hidden cases from the pool
             profiler/       portfolio -> Profile (P2.1): keywords.py (keyword maps),
                             taxonomy.py (dsa/taxonomy.yaml, seed concept
                             vocabulary), profile.py (rules; one generator call
                             only if no domain or no concept); POST /profiles
                             stores it on a new assessment (status "profiled")
             scoring/        correctness.py (pure formulas, passed_ids, bands),
                             score_session.py (ScoreBreakdown from stored submit
                             runs + events; used by submit and POST .../regrade),
                             efficiency.py (AI efficiency E from hint events and runs)
             report/         report details (F3, recruiter key): claims.py (portfolio
                             claims vs tested tasks), build.py (certificates, hidden-test
                             timeline, integrity notes, AI efficiency parts, from stored
                             records), summary.py (one cached generator call, max_tokens
                             300, numbers only: "AI summary, not scored");
                             app/routes/report.py GET /sessions/{id}/report[/summary]
             trail/          Trail Map (F4, report-only): graph.py (ast function spans,
                             name-based call graph), replay.py (focus/edit events ->
                             functions using the snapshot of the moment; visits, dwell,
                             metrics), session.py (load from the DB);
                             app/routes/trail.py GET /sessions/{id}/trail and
                             app/recruiter.py (X-Recruiter-Key check)
             assistant/      hint assistant (F2): hints.py (ladder L1 concept / L2
                             function / L3 line, rising only after a run; 1 per
                             60 s per session, 8 per task; context without reference
                             or hidden tests; assistant slot, max_tokens 300; events),
                             guards.py (extraction regexes, 5 code lines, copydetect
                             similarity to the reference fix -> L1 nudge);
                             app/routes/hints.py: POST .../tasks/{id}/hint, GET .../hints
             migrations/     Alembic (alembic.ini next to it)
             gate/           validation gate (P2.7): core.py (validate/certify,
                             every check), limits.py (all limits), leak.py
                             (statement leak check, also for P2.5), diff.py,
                             stubs.py (DSA stub strength), reference.py,
                             mutation.py (optional mutmut); `make gate`
             llm/ runner/ contracts_gen/ scripts/ tests/
             interviewer/    AI voice interview (F5, never scored): facts.py (candidate's
                             diff -> expected facts, fuzzy match), plan.py (one cached
                             generator call: 2 role, 1 portfolio, 2 submission questions),
                             interview.py (turn rules, interviewer slot max_tokens 120,
                             one follow-up, INTERVIEW_TOKEN_BUDGET), guards.py;
                             app/routes/interviews.py /interviews/{session id}; TTS via
                             llm.client.speech
             A new top-level package must be added to `packages` in
             backend/pyproject.toml and to the mkdir line in backend/Dockerfile.
seeds/       hand-written seed repos, each with tests + concepts.yaml; tests/perf/
             (perf tests + input generator) is used only by Master tasks, as hidden tests
dsa/         DSA bank: one folder per problem (problem.json, problem.md,
             stub.py, reference.py, cases.json; make_cases.py for hand-written
             ones), taxonomy.yaml (canonical topics, synonyms, tiers,
             solved-count thresholds, tier rules), tools/import_leetcode.py
             (`make dsa-import`), raw/ (git-ignored: dataset + LeetCode's
             original descriptions; never commit). Backend only (mounted
             read-only at /dsa); expected answers never reach a sandbox.
             ~1/3 of problems are `"practice_only": true` (dsa_bank.practice_split,
             re-applied by the importer): practice mode shows only those,
             select_problem never picks them
code-compr/  Faiz's code-reading app (Next.js + Prisma, port 3002); showcase/ is the
             landing site (port 3001). coding-assessment/ is archived on the
             archive/coding-assessment branch
runtimes/    Dockerfiles per runtime
sim/         simulated candidate scripts
e2e/         `make e2e`: headless Chromium (Playwright image) drives the demo flow;
             demo.mjs holds the steps and expected scores, run.sh the wiring
docs/        blueprint, prompts, progress, interviewer spec

## Tiers
- novice: 1-file bug fix + easy DSA, no assistant
- adept: 2–3 file feature + medium DSA, assistant enabled
- master: multi-file bug + performance constraint + medium/hard DSA, assistant enabled

## Commands
make up | make down | make migrate | make seed-demo | make e2e | make e2e-practice | make test |
make test-docker | make lint | make contracts | make runtimes | make mutate |
make remove-feature | make build-master | make enrich | make gate | make llm-smoke |
make llm-usage | make dsa-import
(Keep this list in sync with the Makefile.)

- `make seed-demo [TIER=adept]`: builds and validates the P1.3 demo tasks in the
  sandbox, runs the validation gate on both (they must pass; ~2 min), stores an
  assessment for the portfolio fixture, starts its session (the 60-minute
  timer starts now) and prints the session URL. TIER=adept: the domain task is
  the seed's reporting feature removed and enriched (one generator call, cached),
  so the session has the hint assistant.

- `make e2e`: needs the stack up (`make up`). Restarts worker and beat (Celery
  doesn't reload code), runs `make seed-demo`, then headless Chromium:
  starter Run (a visible test fails) → fix both tasks by pasting into the bundled
  Monaco → Run → Submit → report, asserting final 100 / Strong, every visible and
  hidden test passed, run counts, time on task, report = breakdown JSON, Re-grade
  identical. Any request leaving the stack (e.g. a CDN) fails it. ~2 min; a
  failure saves e2e/artifacts/failure.png. Re-run it instead of re-testing the
  browser flow by hand; when a phase changes the flow or the expected scores,
  update e2e/demo.mjs in the same change.

- `make e2e-practice`: needs the stack up. Restarts the worker, then headless
  Chromium on /practice: Run, custom input, Submit (Accepted 35/35) in Python and
  JavaScript, code survives a reload, no request leaves the stack. ~30 s.

- `make migrate`: `alembic upgrade head` on the dev database. A schema change
  means: edit app/models.py → `docker compose run --rm api alembic revision
  --autogenerate -m "..."` → review the file → `make migrate`.
  tests/test_migrations.py fails if models and migrations differ.
- `make test`: backend tests in the api container; starts postgres and redis.
  API tests use their own `<db>_test` database built from the migrations.
- `make test-docker`: runner tests that start real sandbox containers. Runs
  in the worker (the only service with the Docker socket); needs
  `make runtimes` first.
- `make contracts`: regenerate Pydantic and TS types; commit the output.
- `make mutate SEED=... CONCEPT=... [RNG_SEED=0]`: list a seed concept's bug
  candidates, pre-filter them in the sandbox (≤12 runs) and print a validated
  draft Novice task from the best one. Runs in the worker; no LLM calls.
- `make remove-feature SEED=... [CONCEPT=...]`: without CONCEPT, list which
  concepts span 2–3 files; with it, stub that concept, check it in the sandbox
  and print a validated draft Adept task. Runs in the worker; no LLM calls.
- `make build-master SEED=... [CONCEPTS="a b"] [RNG_SEED=0]`: list the seed's perf
  regressions, calibrate the budget (5 reference runs of the perf test, 3 × median),
  keep the first regression that exceeds it and keeps functional tests green, add a
  bug from CONCEPTS in another file, and print the validated draft Master task.
  ~1.5 min in the worker; no LLM calls.
- `make enrich SEED=... TIER=novice|adept [CONCEPT=...] [PORTFOLIO=...]`: build a draft
  task, then enrich it: one generator call (cached) writes the statement and a rename
  map, the leak check rejects a statement that gives the fix away (one retry, then a
  template), renaming is applied only if the sandbox re-run matches. Spends credits on a
  cache miss; the demo tasks are never enriched.
- `make gate TASK=<task_id> [MUTATION=1]`: run the validation gate on the
  newest stored task with that id; prints the certificate (exit 0) or the
  rejection reasons (exit 1). MUTATION=1 adds mutmut (1-3 min). Runs in the
  worker; no LLM calls.
- `make llm-smoke`: one real request per slot; spends credits on a cache miss.
- `make llm-usage`: tokens and estimated spend per slot.
- `make dsa-import`: downloads LeetCodeDataset (pinned revision) into dsa/raw/,
  rebuilds the imported dsa/<id>/ folders, running every reference in the
  sandbox (~3 min). No LLM. `make lint` fails if anything under dsa/raw/ is tracked.

First-time setup: `cp .env.example .env` (fill FEATHERLESS_API_KEY), then
`make runtimes`, `make up` and `make migrate`.
After adding a frontend dependency: `docker compose up -d --build -V frontend`
(-V refreshes the container's node_modules volume).
Files created inside a container (e.g. a generated migration) are owned by
root; fix with `docker compose run --rm --no-deps api chown -R $(id -u):$(id -g) /app`.

## Team
3 members: Sriram Aditya Sai (lead), G Anish, Faiz.
Roles: A Execution (runner, sandbox, API, workers) · B Generation + AI and
scoring · C Frontend + interviewer UI. Person-to-role mapping: TBD.

## Repository and hackathon rules
- Repo: github.com/ROG-user-0987/HFT26-TEAM-41, a fork of
  cbitosc/HFT26-TEAM-41 (CBIT Hacktoberfest '26). Push only to the fork
  (origin). Never push to the upstream cbitosc repo.
- One feature branch per prompt; merge into the fork's main only after its
  acceptance checks pass.
- Open-source libraries are allowed with attribution: add every new library,
  dataset, or borrowed method to ATTRIBUTIONS.md in the same change.
- All code must be written during the hackathon.
- Keep the Team Information section of README.md unchanged.
- Final submission: a PR from the fork's main to upstream main titled
  "[SUBMISSION] TEAM-41 - JL - <track name>", with solution overview,
  architecture and tech stack, local setup, demo video link, screenshots.

## Interviewer rules
- Never affects the final score.
- Never reveals solutions, hidden tests, or reference code.
- Never asks about protected attributes (age, religion, family,
  nationality, health, etc.).
- Uses only recruiter-provided information about the company.
- Requires mic consent, disclosing that browser speech recognition may send
  audio to the browser vendor.
- Stores transcripts, not audio, by default.
- Follows the token budget rules in docs/INTERVIEWER.md.

## Speed rules
- While developing, run only the tests for the files you changed
  (`pytest path/to/test_file.py` or `-k`). Run the full `make test` once, at
  the end.
- Run `make test-docker` only if runner, sandbox, grading, or builder code
  changed, and only once, at the end.
- Run `make e2e` only if the IDE, report, grading, or scoring changed, and
  only once, at the end.
- Never re-run checks after a docs-only change.
- If test suites are parallel-safe, add pytest-xdist (`-n auto`) to
  `make test` and `make test-docker`; skip any suite that isn't.
- Don't explore the repo beyond what the task needs; the layout is in this
  file.
- For small choices, decide, log the decision in docs/PROGRESS.md, and keep
  going. Only stop to ask when a choice conflicts with a rule here.
- Keep the final report under 15 lines: what changed, check results,
  decisions to review, gaps. No tables unless asked.

## Working rules for Claude
- Before finishing any task, run the relevant tests and show the output.
  Never claim something works without running it. Any change that touches the
  candidate IDE, the report, grading or scoring also runs `make e2e`.
- Keep changes scoped to the current prompt. Don't refactor unrelated code.
- Add dependencies only when needed, pin versions, and attribute them.
- Prefer simple, readable code over clever abstractions.
- If a requirement is ambiguous or conflicts with the rules above, stop and ask.
