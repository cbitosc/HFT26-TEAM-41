# Build prompts

Paste one prompt at a time into Claude Code, in order. Every prompt follows
the session protocol in CLAUDE.md (branch, acceptance checks, update
docs/PROGRESS.md, commit, push, merge when green).

Format for any new prompt: goal → requirements → constraints → acceptance
checks Claude must run → report back (what changed, how to verify, gaps).
Phases 0–2.3 are written in full; later items are specifications to be
turned into full prompts against the code as it exists.

## Phase 0: Foundation (done except P0.0, which needs verifying)

- P0.1 Scaffold: compose (postgres, redis, api, worker, frontend), /health, Celery ping, Makefile.
- P0.2 Contracts: JSON Schemas + generated Pydantic/TS types + fixtures.
- P0.3 Featherless client: OpenAI SDK + Instructor, model slots, retries, Redis cache, smoke script.
- P0.4 Runtimes + runner: python311 and node20 images, locked-down run_tests().
- P0.5 Seed repo: seeds/py-fastapi-expenses with tests, concepts.yaml, README_TOUR.md.

### P0.0 Repository setup

```text
Follow the session protocol in CLAUDE.md. Branch: p0-0-repo-setup.

1. README.md:
   - Keep the Team Information and Team Members sections exactly as they
     are. Leave the "Problem Track" field in the table unchanged.
   - In the Problem Statement section, set the title to "Portfolio-Driven
     Adaptive Coding & Technical Assessment Platform" and replace the
     placeholder text with a 5–8 line summary based on docs/BLUEPRINT.md
     section 1.
   - Keep the Contribution & Submission Workflow and rules sections.
   - Add a "Project structure" note: our code lives in backend/, frontend/,
     contracts/, seeds/, dsa/, runtimes/, sim/, docs/ at the root instead of
     the starter's suggested src/, one line per folder.
   - Add placeholder sections, required for the final PR: Solution overview,
     Architecture and tech stack, Local setup, Demo video, Screenshots.
     Mark each "To be completed".
2. LICENSE: MIT, copyright 2026 Team JL (HFT26-TEAM-41).
3. ATTRIBUTIONS.md: every open-source project, dataset, and method actually
   used so far plus those planned in docs/BLUEPRINT.md section 7, each with
   link and license, grouped as "Used as dependencies", "Methods we
   adapted", "Planned".
4. .gitignore for Python, Node/Next.js, .env files, editor folders, OS
   files, Docker volumes, coverage output (merge with any existing one).

Acceptance checks:
- Show the README diff; confirm the Team Information lines are unchanged
- List added files
- docs/PROGRESS.md updated, branch pushed, merged to main if green
```

## Phase 1: Walking skeleton

### P1.1 Database and API

```text
Follow the session protocol in CLAUDE.md. Branch: p1-1-db-api.

1. SQLAlchemy models in backend/app/models.py + Alembic migration in
   backend/migrations/:
   assessments (id, candidate_name, portfolio JSON, tier, status, created_at),
   tasks (id, assessment_id, spec JSON matching task_spec, order),
   sessions (id, assessment_id, started_at, deadline_at, submitted_at, status),
   file_snapshots (id, session_id, task_id, ts, files JSON),
   events (id, session_id, task_id, ts, type, payload JSON), append-only,
   runs (id, session_id, task_id, kind visible|silent|submit, result JSON, ts),
   scores (id, session_id, computed_at, breakdown JSON).
   Index events on (session_id, ts).
2. API routes in backend/app/routes/:
   - POST /sessions {assessment_id}: starts a session; server sets
     deadline_at = now + 60 min. Starting twice returns the same session.
   - GET /sessions/{id}: status, server time, deadline, task list.
   - GET /sessions/{id}/tasks/{task_id}: candidate_task_view ONLY, via a
     dedicated to_candidate_view(spec) with a test proving it never includes
     reference_ref, hidden_tests, or certificate internals.
   - PUT /sessions/{id}/tasks/{task_id}/files: autosave snapshot.
   - POST /sessions/{id}/events: batch validated against the event schema;
     rejected after the deadline.
   - POST /sessions/{id}/tasks/{task_id}/run: enqueue a run job, return job id.
   - POST /sessions/{id}/submit: enqueue full grading.
   - GET /jobs/{id}: job status and RunResult (visible results only).
   Every write after deadline_at returns 409.
3. Tests for each route, including deadline rejection and the leak test.

Acceptance checks:
- `alembic upgrade head` works on a fresh database
- `make test` passes
- curl sequence: create session → fetch task → save files → post events
```

### P1.2 Worker jobs (amended: hidden tests isolated, anti-tampering)

```text
Follow the session protocol in CLAUDE.md. Branch: p1-2-workers.

1. run_job(session_id, task_id, files):
   - Build the workspace: starter files, then the candidate's files filtered
     through the editable allowlist (step 4), then the visible test files
     from the backend copied over the top.
   - Run visible tests → run kind "visible".
   - Run hidden tests in a SEPARATE container where the hidden test files are
     added (read-only). Output is never returned anywhere → run kind
     "silent". Hidden files are never present in the visible run, so
     nothing the candidate prints can leak them.
   - One "run" event: visible {passed,total}, hidden_silent
     {passed,total,failing_ids}.
   - The job result returned to the API: ONLY the visible RunResult.
   - At most one active run per session; a second Run while one is queued
     or running returns 429.

2. submit_job(session_id): for each task, latest snapshot → same workspace
   rules → visible + hidden runs → run kind "submit" → "submit" event →
   scoring stub (store per-task pass counts). The session is already locked
   by the submit route; make submit_job idempotent if it's retried.

3. Celery beat auto-submit every 30 s for sessions past their deadline.

4. Anti-tampering (keep each check simple and unit-tested):
   a) Editable allowlist: only paths present in the task's starter_files are
      editable. Enforce at save time (reject other paths with 422 and a clear
      message) and again at run time (drop anything else). Always drop test
      dirs, conftest.py, pytest.ini, tox.ini, setup.cfg, pyproject.toml
      changes, sitecustomize.py, usercustomize.py, *.pth, and for Node:
      package.json, jest.config.*, babel config, .npmrc.
   b) Expected test IDs: the set of collected test IDs must exactly match
      the IDs expected for the visible or hidden set (derive them from the
      task's test files when the task is built, and store them on the spec).
      Any mismatch → status "error" with reason "test_set_mismatch"; never
      count it as passes.
   c) Report path: write the JSON report to a random filename per run,
      outside /workspace, passed on the command line.
   d) Suspicious-code scan of the candidate's changed files: flag
      _pytest, sys.modules, os._exit, sys.exit at module level, builtins
      patching, importlib tricks, and file writes outside /workspace. Store
      it as an integrity note on the run; never block or score on it.

5. Confirm session IDs are UUID4 (not sequential); add a test.

6. Never return hidden stdout/stderr, hidden test names, or hidden failure
   messages to the API.

Tests:
- run_job stores both runs and one event; API response has no hidden data
- A saved tests/test_x.py or conftest.py is rejected at save time and
  ignored at run time
- A candidate conftest that forces passes has no effect (it's dropped)
- Test-ID mismatch produces status "error", not passes
- A second concurrent Run returns 429
- submit_job uses the latest snapshot and is idempotent
- auto-submit fires for an expired session

Acceptance checks:
- `make test`, `make test-docker`, `make lint` pass
- Show the event row and the stored run rows for one real run
```

Implemented in backend/app/: grading.py (run, submit, auto-submit, test-id
check, derive_test_ids for builders), workspace.py (allowlist, workspace
assembly), integrity.py (scan), jobs.py (run lock), celery_app.py (beat
schedule), worker.py (Celery tasks). Contracts: TaskSpec.visible_test_ids /
hidden_test_ids, RunResult.reason. Builders (P1.3, P2.x) must fill the test
ids with grading.derive_test_ids.

### P1.3 Hard-coded demo task (amended: reuse P1.2's task, isolated DSA answers)

```text
Follow the session protocol in CLAUDE.md. Branch: p1-3-demo-task.

1. Domain task, backend/builder/manual.py. Reuse what P1.2 already built for
   its demo task (the seed_spec fixture in tests/test_grading_docker.py and
   the scratch builder used for its acceptance run): move it here and make
   the tests import it instead of duplicating it.
   - Novice task from seeds/py-fastapi-expenses: off-by-one bug in
     app/utils.py::paginate via a small deterministic AST transform.
   - Split: about a third of the PAGINATION tests visible, including at
     least one that fails on the starter; the remaining pagination tests
     plus all other seed tests hidden, so hidden tests exercise the same bug.
     (Test files are the unit of a run: put the visible pagination tests and
     the hidden ones in separate files, extracted with AST.)
   - Fill visible_test_ids and hidden_test_ids with grading.derive_test_ids.
   - Hand-written statement_md, repo tour, target_symbols, entry_symbols.

2. DSA task "longest substring without repeating characters"
   (sliding_window): Python stub, 5 visible + 30 hidden cases. Expected
   answers must never enter the sandbox:
   - The in-container harness receives only inputs (a JSON list of
     {id, input}), calls the candidate's function on each one with a
     per-case timeout, and writes {id, output | error} to the random report
     path in /runner-out.
   - The backend compares outputs with the expected values outside the
     sandbox, producing a normal RunResult (one test per case id).
   - Missing or extra case ids → error / test_set_mismatch, as in P1.2.
   - Output comparison is exact by default, with an optional per-problem
     comparator (e.g. unordered lists, float tolerance) stored in the spec
     (contract change: update the schema, `make contracts`, fixtures).
   - visible_test_ids / hidden_test_ids are the case ids.
   - Test: a candidate function that tries to read a cases file finds no
     expected values anywhere in the container.

3. `make seed-demo` creates the assessment for the portfolio fixture and
   prints the session URL.
4. Validate: starter fails ≥1 visible test; the seed passes everything.

Acceptance checks:
- `make seed-demo` prints the URL and both validation results
- The DSA "no expected values in the container" test passes
```

Implemented in backend/builder/ (manual.py, seed_demo.py), backend/app/dsa.py,
backend/runner/harness/python_cases.py and dsa/longest_unique_substring/. Contract:
TaskSpec.dsa_cases.comparator. The sandbox runner gained run_program (any command that
writes a JSON report), which run_tests and the DSA harness share.

### P1.4 Candidate IDE

```text
Follow the session protocol in CLAUDE.md. Branch: p1-4-ide.

Session page at frontend/app/session/[id]/:
- Left: task tabs (domain, DSA), rendered statement, repo tour.
- Center: file tree + Monaco (@monaco-editor/react) with file tabs.
- Bottom: test results (pass/fail per test, messages).
- Top bar: countdown from the server deadline (resync every 30 s), Run,
  Submit, autosave status.
Editable files: only starter files outside tests and test/package config
(backend/app/workspace.py); show the rest read-only and never send them, or
the save returns 422. A Run while another is in flight returns 429.
Behavior: autosave every 5 s and on Run; Run → POST → poll /jobs/{id} every
1 s → show the visible results as soon as `result` is non-null (status may
still be "running" while hidden tests run); re-enable Run when status is
"done" or "failed"; Submit → confirm → "submitted" screen; at the
deadline lock the editor and show "Time's up — submitted."
Telemetry (frontend/lib/telemetry.ts): focus sampled once per second (file,
line; symbol null), edit aggregated per second (file, chars_added,
chars_removed), paste (chars), blur. Batch; POST every 5 s and on unload
(sendBeacon). Use generated TS types. Tailwind, simple. No assistant yet.

Acceptance checks:
- `npm run build` passes with no type errors
- With the `make seed-demo` URL: fix the bug, Run, see more passes, Submit;
  describe what the UI showed
- Event counts per type for that session
```

### P1.5 Basic scoring and report

```text
Follow the session protocol in CLAUDE.md. Branch: p1-5-scoring.

1. backend/scoring/correctness.py (pure, unit-tested):
   correctness = 100 × (0.3 × visible_rate + 0.7 × hidden_rate) × perf_factor;
   perf_factor 1.0 without perf spec, else 1.0 within budget → 0.5 at 3×
   budget → 0.5 beyond. Edge cases: zero tests, all pass, all fail.
2. backend/scoring/score_session.py: per-task correctness from submit runs,
   time per task (first focus to last edit), run count, final score (Novice:
   mean correctness) → scores.breakdown. Reads stored records only. No LLM.
3. POST /sessions/{id}/regrade; test that two regrades give byte-identical JSON.
4. frontend/app/report/[id]/: final score, band (Strong ≥ 80, Pass ≥ 60,
   Borderline ≥ 45, Not yet), per task: visible/hidden pass rates, time, runs.

Acceptance checks:
- `make test` passes, including the determinism test
- Report for the demo session matches the breakdown JSON
```

Implemented in backend/scoring/ (correctness.py, score_session.py), backend/app/routes/scores.py
(GET /sessions/{id}/score, POST /sessions/{id}/regrade), contracts/score_breakdown.schema.json
and frontend/app/report/[id]/. The submit job stores the breakdown. `make e2e` (e2e/) drives
the whole demo in headless Chromium and checks the report against the breakdown JSON; later
prompts re-run it instead of re-testing the browser flow by hand, and update e2e/demo.mjs when
they change the flow or the expected scores.

## Phase 2: Generation + gate

### P2.1 Taxonomy and profiler

```text
Follow the session protocol in CLAUDE.md, including the token policy.
Branch: p2-1-profiler.

1. dsa/taxonomy.yaml: ~20 canonical topics (arrays, hashing, two_pointers,
   sliding_window, stack, queue, linked_list, binary_search, trees, bst,
   heaps, graphs_bfs_dfs, shortest_paths, dp, greedy, backtracking, tries,
   union_find, bit_manipulation, intervals) with synonyms and allowed tiers.
   Configurable thresholds: easy ≥1 solved, medium ≥5, hard ≥15.
2. contracts/profile.schema.json + `make contracts`: domain (backend | web |
   ml | security), runtime (python311 | node20), concepts (from the concept
   vocabulary only), allowed_topics per tier, suggested_tier + reason,
   unsupported_notes.
3. backend/profiler/:
   - Concept vocabulary = union of concepts in seeds/*/concepts.yaml.
   - Runtime and domain from keyword maps over keywords, skills,
     descriptions. Unsupported stacks map to the closest runtime with a note.
   - Concepts by deterministic keyword/synonym matching.
   - LLM fallback only when rules give no domain or zero concepts: one
     generator call, answers chosen from given lists (enums), max_tokens 150,
     temperature 0, cached, logged.
   - suggested_tier from solved counts and project count (documented rules).
   - POST /profiles {portfolio} → Profile, stored on the assessment.
Tests (LLM mocked): fixtures for Python backend, React web, ML, security,
messy topic names, unsupported stack (Go); LLM not called when rules
succeed, called once for a vague portfolio; threshold cases (4 dp → not
medium; 15 → hard).

Acceptance checks:
- `make test` passes; show the Profile for each fixture
```

Implemented in backend/profiler/ (keywords.py, taxonomy.py, profile.py, `python -m profiler
FILE...` prints profiles), dsa/taxonomy.yaml (22 topics; thresholds and tier rules are
configurable there), contracts/profile.schema.json, POST /profiles (backend/app/routes/
profiles.py; migration 0003 adds assessments.profile). Portfolio fixtures for every case are
in contracts/fixtures/portfolio.valid.*.json. Allowed topics per tier use the tier's
difficulty (novice easy ≥1, adept medium ≥5, master hard ≥15). `sources` records whether
each inferred field came from the rules, the LLM fallback or a default.

### P2.2 Mutation engine (Novice)

```text
Follow the session protocol in CLAUDE.md. Branch: p2-2-mutation.
No LLM calls in this prompt.

1. Use LibCST (formatting-preserving); pin it; add to ATTRIBUTIONS.md.
2. backend/builder/mutate.py operators (each unit-tested): comparison flip,
   off-by-one (±1 on integer constants / index arithmetic), boolean operator
   swap, removed guard, swapped same-typed call arguments, wrong return.
3. inject_bug(seed_id, concept, rng_seed) → candidates: targets from the
   seed's concepts.yaml; every applicable site enumerated, ordered
   deterministically by rng_seed; each with starter_files (only the changed
   file differs), unified diff, target_symbols, operator, line.
4. Cheap pre-filter with backend/runner: keep mutants that import, fail ≥1
   test and ≤40% of tests; prefer 1–5 failing tests. Cap runner calls per
   request (default 12).
5. Visible/hidden split: ~1/3 of the concept's tests visible, including at
   least one test that fails on the starter.
6. Draft task_spec (mode "seed", tier "novice", statement placeholder for
   P2.5). manual.py uses engine output, keeping the hand bug as fallback.
7. `make mutate SEED=py-fastapi-expenses CONCEPT=pagination` prints candidates.
Tests: each operator; same rng_seed → identical output; ≥3 valid candidates
for pagination.

Acceptance checks:
- `make test` passes; show `make mutate` output
```

Implemented in backend/builder/mutate.py (operators, inject_bug, prefilter, ranked,
draft_novice_task; `python -m builder.mutate SEED CONCEPT`) and backend/builder/tasks.py
(shared with manual.py: concepts.yaml loading, starter files, the concept-wide visible/hidden
split, validate_task). manual.py takes the engine's off-by-one candidate at paginate()'s
offset, byte-identical to the P1.3 bug, so the demo and `make e2e` are unchanged.

### P2.3 Feature removal (Adept)

```text
Follow the session protocol in CLAUDE.md. Branch: p2-3-feature-removal.
No LLM calls in this prompt.

1. backend/builder/remove_feature.py: remove_feature(seed_id, concept) →
   draft task_spec (tier "adept", mode "seed"). Only concepts whose symbols
   span 2–3 files are eligible (else a clear error listing eligible ones).
   Each target body becomes: signature + docstring +
   `raise NotImplementedError("TODO: <first docstring line>")` (LibCST).
   Missing docstrings → add them to the seed (re-run its tests).
2. Runner checks: app imports; non-target concepts' tests pass; target tests
   fail on the starter and pass on the seed.
3. ~1/3 of the concept's tests visible; record scope_files (2 or 3).
4. `make remove-feature SEED=... CONCEPT=...`. If no concept spans 2–3
   files, say which seed changes would create one.
Tests: eligible vs ineligible concepts; import; non-target pass; target fail.

Acceptance checks:
- `make test` passes; show `make remove-feature` output
```

Implemented in backend/builder/remove_feature.py (`python -m builder.remove_feature SEED
[CONCEPT]`). Targets are a concept's functions and non-dunder methods; data classes and
type aliases stay as the interface. In py-fastapi-expenses, auth and reporting span 2-3
files; auth is rejected by the runner check (every endpoint depends on it), reporting
becomes the Adept draft. Docstrings were added to repo.find_user_by_token and
routes.get_monthly_report.

### P2.4 Master builder

```text
Follow the session protocol and speed rules in CLAUDE.md. Branch:
p2-4-master. Replace the P2.4 spec in docs/BUILD_PROMPTS.md with this
prompt. A teammate is working on P2.6 in dsa/ in parallel: stay within
backend/builder/, backend/scoring/ (perf wiring only), and seeds/. No LLM calls.

Master tier = one bug plus one performance regression, in different files.

1. Seed prep (seeds/py-fastapi-expenses):
   - In concepts.yaml, mark 2–3 perf-sensitive symbols (e.g. filtering,
     monthly report) with perf: true.
   - Add tests/perf/gen_large.py producing a large deterministic dataset
     (e.g. 50,000 expenses) and a perf test that times the target operation
     with time.perf_counter (best of 3) and records the measured ms with
     pytest's record_property.
   - All seed tests, including perf, must pass on the reference.
2. backend/builder/master.py, with LibCST perf-regression operators (each
   unit-tested): dict/set lookup → list scan; cache bypass; per-item query
   in a loop (N+1); quadratic de-duplication.
   build_master(seed_id, concepts, rng_seed) = one P2.2 bug + one perf
   regression in a different file. Reuse P2.2's engine and
   grading.derive_test_ids.
3. Calibration in the runner: run the reference perf test 5 times; set
   budget_ms = 3 × median. The regressed starter must exceed the budget;
   otherwise reject that regression and try the next site. Store
   perf.budget_ms, perf_ref_ms and perf_naive_ms in the spec for the
   certificate.
4. Perf tests are hidden. The statement (a placeholder until P2.5) states
   the budget. Submit runs must record perf_ms, and backend/scoring must
   use it for perf_factor instead of "within budget until measured".
5. `make build-master SEED=py-fastapi-expenses` prints the task summary
   and calibration numbers.

Tests: each perf operator; calibration rejects a regression that doesn't
exceed the budget; the reference passes everything including perf;
perf_factor uses the measured perf_ms.

Acceptance checks: make test, make test-docker, and make e2e once at the
end (scoring changed). Show make build-master output.
```

Implemented in backend/builder/master.py (`python -m builder.master SEED [CONCEPT ...]
[--rng-seed N]`) and backend/builder/perf.py (perf_ms from pytest-json-report
`user_properties`). The seed gained a bulk import (`POST /expenses/import`, concept
importing) as its perf-sensitive code; concepts.yaml `perf_symbols` lists
services.import_expenses and services.monthly_report with their perf tests. All four
operators find a site in the seed; with rng_seed 0 calibration rejects the quadratic
de-dup (within budget) and keeps the list scan (~2.8× budget).

### P2.5 LLM enrichment

```text
Follow the session protocol and speed rules in CLAUDE.md, especially the
token policy. Branch: p2-5-enrich. Replace the P2.5 spec in
docs/BUILD_PROMPTS.md with this prompt. A teammate owns DSA rewriting in
P2.6: this prompt covers domain tasks only.

backend/builder/enrich.py: enrich(draft_spec, profile) → the spec with a
statement, repo tour, and (when safe) renamed entities.

1. Statement: ONE generator-slot call per task, structured output, cached
   by input hash, max_tokens 500, temperature 0.2. Input only: the unified
   diff, target symbol names, visible failing test names with the last 20
   lines of their messages, the tier, and the candidate's project names.
   Output: an issue-style statement (symptoms and expected behavior, at most
   200 words) that never states the fix. For Master, code (not the LLM)
   appends the perf budget sentence.
2. Leak check (plain code): reject the statement if it contains any changed
   line from the reference side of the diff, or the exact operator/value
   that fixes the bug. On rejection, retry once; then fall back to a
   template statement built by code.
3. Repo tour: copy the seed's README_TOUR.md. No LLM.
4. Entity renaming, in the same LLM call: concepts.yaml lists renamable
   domain terms per seed (e.g. expense, category). The model returns a
   rename map limited to those terms, matching the candidate's projects
   (e.g. expense → order). Apply it mechanically with LibCST to code and
   tests (identifiers, strings, routes), update target_symbols and
   entry_symbols, re-derive test IDs, and re-run reference and starter. If
   any result differs from the un-renamed version, drop the renaming and
   keep the original names.
5. Extra LLM-written hidden tests: behind a flag, off by default (token
   cost). When on, keep only tests the reference passes.
6. The hand-built seed-demo task in backend/builder/manual.py is NOT
   enriched, so make e2e keeps working unchanged.

Tests (LLM mocked): the leak check catches a statement containing the fix;
the template is used after two failures; renaming keeps all test results
identical; a cache hit makes no second call; the demo task is untouched.

Acceptance checks: make test and make test-docker once at the end. With the
real key, enrich one Novice and one Adept task; show both statements, the
rename maps, and the tokens spent (make llm-usage).
```

Implemented in backend/builder/enrich.py (`make enrich SEED=... TIER=novice|adept`).
enrich(draft_spec, profile, project_names): project names come from the portfolio (the
Profile has none). The model gets the starter side of the diff only (context and `+`
lines; reference code never enters a model's context, CLAUDE.md rule 2) plus the repo
tour's first paragraph; the leak check compares against the full reference side in code.
Since P2.7 the leak check lives in backend/gate/leak.py and nowhere else: enrich.py
calls leak.statement_problems() (leaks() plus the 200-word limit, STATEMENT_MAX_WORDS in
gate/limits.py) on the evidence from leak.fix_evidence(), so enrichment and the gate judge
statements the same way. Tests: tests/test_gate.py (leak section) and tests/test_enrich.py.
Renamed tasks record the map in reference_ref (`seeds/<seed>?rename=old:new,...`), which
enrich.reference_files() resolves. Real runs: Novice pagination → expense→inventory,
category→department; Adept reporting → expense→item, category→group; both renamings
re-verified in the sandbox. 4 generator calls, 2,590 tokens in / 549 out, $0.000516.

### Specs for the rest of Phase 2

- **P2.6 DSA:** written in full below ("P2.6 DSA bank, runners, rewriting").
- **P2.7 Validation gate + certificate:** written in full below ("P2.7
  Validation gate and certificate").
- **P2.8 AI solve-rate probe:** probe slot attempts each task 3 times without
  hints, graded by tests; ai_solve_rate and difficulty_index; configurable
  rejection thresholds per tier; only for tasks that passed the gate.
- **P2.9 Builder pipeline + recruiter page:** Celery job orchestrating
  P2.1–P2.8; repair loop (≤2 tries); fallback bank; recruiter page to upload
  a portfolio, choose a tier, preview tasks and certificates, get the link.

### P2.6 DSA bank, runners, rewriting

Follow the session protocol and speed rules in CLAUDE.md, especially the
token policy. Branch: p2-6-dsa.

Goal: a tagged DSA problem bank, tier- and topic-bounded selection, problems
rewritten into the candidate's domain, and Python + JS grading through the
existing input-only harness from P1.3.

1. Ingestion (no LLM):
   - Script dsa/tools/import_leetcode.py + `make dsa-import`, downloading
     LeetCodeDataset (github.com/newfacade/LeetCodeDataset or its Hugging
     Face copy) at a pinned commit/revision. Attribute it in ATTRIBUTIONS.md.
   - Never exec or eval dataset content outside the sandbox. Parse case
     input strings with the ast module (keyword-argument parsing only);
     drop anything that doesn't parse cleanly.
   - Keep only problems whose parameters and return values are JSON types
     (int, float, bool, str, lists/dicts of those; no ListNode, TreeNode, or
     class-design problems) and whose tags ALL map to dsa/taxonomy.yaml.
   - Target 80–120 problems spread across tiers. Difficulty → tier:
     Easy → novice, Medium → adept, Medium + Hard → master.
   - Recompute every expected value by running the dataset's reference
     solution in the sandbox; drop problems where they disagree or time out.
   - Licensing: original problem descriptions are LeetCode's text. Store
     them only in a git-ignored local cache (dsa/raw/), used as rewrite
     input; never commit them, never serve them.

2. Bank format: follow the existing dsa/longest_unique_substring/ layout
   from P1.3 so the current harness and builder work unchanged, and move
   that problem into the bank as well. Each problem: id, tags, tier(s),
   entry point, typed signature, reference solution, cases
   ({id, input, expected}), comparator (unordered_list if the description
   says "any order", float_tolerance for float returns, else null).
   Committed: everything except the original description.

3. Selection: select_problem(profile, tier, rng_seed) returns only problems
   whose EVERY tag is in profile.allowed_topics for that tier. If none
   qualify, fall back to the easiest problem whose tags are all allowed at
   any lower tier, and record why.

4. Rewriting (one generator call per (problem, domain), cached by input
   hash, max_tokens 600, temperature 0.2, structured output): a story
   statement in the candidate's domain, a new function name, and new
   parameter names (1:1 mapping, valid identifiers in both Python and JS).
   Input: the cached original description, the signature, and the domain
   plus the candidate's project names. Code, not the LLM, inserts two worked
   examples from the visible cases. Validate: the reference wrapped with the
   new names gives identical outputs on all cases; otherwise retry once,
   then use a template statement built by code. If dsa/raw/ is missing,
   use the template statement and log it.

5. Visible and hidden cases: 5 fixed visible cases. At submit, sample the
   hidden cases from the problem's hidden pool (up to 30), seeded per
   session; store the seed AND the selected case ids so re-grading is
   byte-identical. Expected values never enter the sandbox (as in P1.3).

6. JS harness: a Node harness mirroring the Python one (inputs only,
   per-case timeout, outputs to the random report path). Candidates
   export the function with module.exports. Same case ids, same
   comparator, same test_set_mismatch rules.

7. Contracts: add only what's needed and regenerate: the problem id, the
   name mapping, and the hidden-case seed and selected ids for a session.

Tests (LLM mocked):
- Selection never returns a problem with an unclaimed or disallowed tag
- Rewritten names map 1:1; validation catches a broken mapping and falls
  back to the template
- Python and JS harnesses give identical results for the same correct and
  wrong solutions on 3 problems
- Re-grade after a sampled submit is byte-identical
- Nothing from dsa/raw/ is ever committed (a check in make lint)

Acceptance checks: run make test, make test-docker, and make e2e once at the
end. Show: bank counts per tag and per tier, one rewritten problem for a
backend profile, and the tokens spent (make llm-usage).

### P2.7 Validation gate and certificate

Follow the session protocol and speed rules in CLAUDE.md. Branch:
p2-7-gate. A teammate may be working on P2.4 (master builder) and P2.5
(enrichment) in parallel: git pull first, and stay within backend/gate/,
contracts, and tests. No LLM calls.

backend/gate/: validate(spec, profile) → (certificate, []) on success, or
(None, reasons) with machine-readable reasons the P2.9 repair loop can act
on (e.g. {"code": "starter_passes", "detail": ...}).

Domain tasks:
- The reference passes visible + hidden 3 runs in a row (any difference =
  flaky = reject).
- The starter fails at least 1 visible test.
- Novice: the starter passes every test outside the target concept.
- Scope, from the starter-vs-reference diff: Novice exactly 1 file and
  ≤10 changed lines; Adept 2–3 files; Master ≥2 files AND perf calibration
  present. Limits configurable in one place.
- Master (only when perf fields are present): budget_ms set, reference
  within budget, starter over budget.
- Test IDs derive cleanly and match the spec.
- Statement leak check: backend/gate/leak.py owns it. Reject if the
  statement contains any changed line from the reference side of the diff,
  or the exact operator/value that fixes the bug. If P2.5 on main already
  has a leak check, move it here and make enrich.py import it; if not,
  write it here and note in docs/BUILD_PROMPTS.md (P2.5) that enrichment
  must use backend/gate/leak.py.

DSA tasks:
- Every tag is in profile.allowed_topics for the task's tier.
- The reference passes all cases using the rewritten names.
- Test strength: trivial stubs (return the first argument, an empty value
  of the return type, 0, None) each fail at least 90% of cases. Record the
  weakest stub's failure rate in the certificate.
- The statement contains no original parameter or function names.

Certificate (contract update + make contracts):
- reference_pass "n/n x3", starter_fail "k/n visible", scope_files,
  changed_lines, perf_ref_ms / perf_naive_ms / budget_ms when present.
- Replace bruteforce_agree with stub_fail_rate (DSA); keep old stored data
  valid (optional field).
- mutation_score: null when not measured (replacing the 0.0 placeholder),
  and the report page shows "not measured" instead of a number.
- Optional mutation testing (flag, default off): mutmut on the reference
  with the task's tests; fill mutation_score when run.

`make gate TASK=<task_id>` validates a stored task and prints the
certificate or the reasons. Also validate the seed-demo tasks (they must
pass).

Tests: each check passes on a good task and fails on a purpose-built bad
task (starter passes, flaky reference, wrong scope, leaked statement,
disallowed tag, weak DSA tests, missing perf for master).

Acceptance checks: make test, make test-docker, and make e2e once at the
end (the report page changed). Show one accepted certificate per task kind
and one rejected task with its reasons.

Amendments (decided during the session):
- The demo bug `offset = page * page_size` also failed 10 filtering,
  sorting and auth tests, so it could not pass the Novice rule. The demo
  now uses the engine's candidate `offset = (page - 2) * page_size`: 3
  failing tests, all pagination ones (1 visible, 2 hidden). builder/manual.py
  and e2e/demo.mjs updated; the fix is the same line.
- Novice and Adept: the starter must fail at least 1 visible AND at least 1
  hidden test.
- The gate records the test ids that fail on the starter ("fail_to_pass",
  visible and hidden) and those that pass on it ("pass_to_pass") in the
  spec (gate.certify). The next prompt changes scoring to use them.
- P2.5 merged with its own leak check in enrich.py: it moved to
  backend/gate/leak.py (one implementation: token matching, both builds'
  fragment rules, including the fix span with one token of context on each side, and
  the 200-word limit for generated statements via statement_problems) and enrich.py
  imports it with no copy of its own. The gate also resolves P2.5's
  renamed references (`seeds/<seed>?rename=old:new,...`), renaming the
  target concept's symbols and tests for the Novice rule.

### P2.7b fail_to_pass scoring

Follow the session protocol and speed rules in CLAUDE.md. Branch: p2-7b-f2p-scoring.

Scoring currently gives credit for tests that already pass on the starter, so an
untouched starter scores about 76. Switch to SWE-bench-style scoring using the
fail_to_pass and pass_to_pass IDs the gate now records:

correctness = 100 × (0.3 × visible_f2p_rate + 0.7 × hidden_f2p_rate) × regression_factor × perf_factor
- f2p_rate = share of fail_to_pass tests that now pass.
- regression_factor = share of pass_to_pass tests that still pass (breaking working code
  costs points).
- If one set has no fail_to_pass tests, the other carries the full weight.
- DSA: every case fails on the stub, so all cases are fail_to_pass; behavior is unchanged.
- Tasks stored before this change, without the IDs: derive them from the stored starter
  run, or fall back to the old formula and log it.

Update docs/BLUEPRINT.md section 5. Tests: an untouched starter scores 0; a full fix
scores 100; a fix that breaks one passing test loses points; DSA unchanged; re-grade stays
byte-identical.

Acceptance checks: make test, then make e2e once at the end (expected scores may change;
update e2e/demo.mjs if so).

## Phase 3: Assistant + scoring

F2 (2026-10-31) replaces P3.1-P3.6: hint endpoint POST /sessions/{id}/tasks/{task_id}/hint
{question}, Adept/Master only, assistant slot, max_tokens 300; context = statement,
visible test names and output, editable files near the target (from level 2), never the
reference or hidden tests; ladder L1 concept, L2 function, L3 line, rising only after a
run since the last hint. Guards: extraction regexes -> refusal + guard_block; copydetect
similarity of reply code vs the reference -> L1 nudge; max 5 code lines; 1 hint per 60 s,
8 per task; hint events logged. Chat panel with assistant-ui. AI efficiency from section 5
of the blueprint in backend/scoring (efficiency.py), re-grade identical. Code:
backend/assistant/, backend/app/routes/hints.py, frontend/app/session/[id]/AssistantPanel.tsx.
P3.5 (simulated candidates) and P3.6 (promptfoo) were not built.

- **P3.1 Hint endpoint + ladder:** L1 conceptual, L2 names a function, L3
  names a line; level rises only after a test run since the last hint.
  Context: statement, visible tests, current files (only those relevant),
  last 40 lines of visible output. Never reference or hidden tests.
  max_tokens ~250.
- **P3.2 Guards:** input rules first, a short classifier call only if rules
  are unsure; output check with copydetect similarity against the reference
  (block above threshold), ≤5 code lines, no complete function bodies; rate
  limit (1 per 60 s, 8 per task); log hint_request, hint_response,
  guard_block with function names mentioned.
- **P3.3 Assistant panel UI** (Adept/Master only), current hint level, note
  that efficient use scores best.
- **P3.4 AI efficiency score:** formula in docs/BLUEPRINT.md section 5; pure
  functions with tests; wired into scoring and re-grade.
- **P3.5 Simulated candidates:** four profiles (independent, good AI user,
  over-reliant, extractor) playing real sessions through the API; mostly
  scripted to save tokens.
- **P3.6 promptfoo:** attack config against the hint endpoint (extraction,
  jailbreak); small run; save the report for the demo.

## Phase 4: Report, Trail Map, interviewer

F3 (2026-10-31) replaces P4.1-P4.3 and P4.6: report page with shadcn/ui and Recharts:
certificate card per task, claim verification map (each portfolio claim vs what was tested
and the result), hidden-test progress timeline with Run and hint markers, integrity notes
(pastes, blurs, flags) labelled "not scored", AI efficiency breakdown, and a 4-sentence
recruiter summary from one cached generator call (max_tokens 300) over the computed
numbers only, labelled "AI summary, not scored". Code: backend/report/,
app/routes/report.py, frontend/app/report/[id]/InsightsTab.tsx, components/ui/.

F4 (2026-10-31) replaces P4.4-P4.5: backend/trail/ (Python ast -> function spans and a
name-based call graph per task; focus/edit events mapped to functions), report-only
metrics (time to first target visit, off-path time before it, found independently vs
within 2 min after a hint, edit precision), GET /sessions/{id}/trail behind
RECRUITER_API_KEY, and a Trail Map tab on the report with React Flow (nodes grouped by
file, target highlighted, animated trail styled differently after hints, dwell heat,
scrubber and play button, metric cards).

- **P4.1** Certificate view (recruiter page + report).
- **P4.2** Claim verification map.
- **P4.3** Progress timeline + hint ROI chart.
- **P4.4** Trail Map builder: tree-sitter per seed → spans, call graph,
  fixed layout; map focus/edit events to symbols; metrics.
- **P4.5** Trail Map replay UI: graph, trail before/after hints, dwell heat,
  scrubber, play, metric cards.
- **P4.6** Integrity flags: large pastes, tab blurs, single-jump pattern.
  Display only.
- **P4.7** Interview plan generator, with per-role question caching
  (docs/INTERVIEWER.md).
- **P4.8** Interview turn endpoint: state machine, deterministic router,
  minimal LLM decision, token budget, guardrails, logging.
- **P4.9** Voice I/O: Featherless TTS proxy with caching; TTS and
  interviewer model-selection scripts; browser speech-recognition hook.
- **P4.10** Interview UI: consent, orb, captions, push-to-talk, controls.
- **P4.11** Interview report tab: transcript, consistency check, token usage.
- **P4.12** Optional faster-whisper fallback.

## Phase 5: Polish + demo

- **P5.1** Pre-generate demo assessments; warm the LLM and TTS caches.
- **P5.2** Error handling and resilience: reconnect, retries, clear messages.
- **P5.3** Demo checklist, seeded simulated sessions, backup recording,
  README sections for the final PR.
