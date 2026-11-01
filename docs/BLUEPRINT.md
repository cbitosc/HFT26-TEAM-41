# Project blueprint: portfolio-driven coding assessment platform

As of 2026-10-31. This file, docs/BUILD_PROMPTS.md, docs/PROGRESS.md and
docs/INTERVIEWER.md are the single source of truth. Update them when a
decision changes.

## 1. Problem statement and requirements

We turn a candidate's structured JSON portfolio into a validated 60-minute
coding assessment in their own domain and stack, then grade it
deterministically. The core goal is **verification**: static tests ignore a
candidate's background, and AI coding tools make it hard to tell whether
candidates understand the work in their portfolio.

| # | Requirement | What it means for us |
| --- | --- | --- |
| 1 | Portfolio intake and personalization | JSON portfolios (projects, stacks, skills, DSA topics solved). Tasks match the domain (Web, ML, Security, Backend) and stay strictly within claimed DSA topics, across three tiers. |
| 2 | Dynamic coding environment | Runnable tasks with starter code in the candidate's stack, testing support, isolated sandboxes. |
| 3 | Deterministic validation and grading | Reference passes and starter fails before release. Grading uses tests, assertions, and security scripts only. LLMs never judge correctness. |
| 4 | Guarded AI assistant (Adept, Master) | Hints without revealing solutions. AI efficiency score up to 20% of the final score, computed from logs. |
| — | Expected outcome | Report with task-wise metrics, pass rates, time taken, AI efficiency, final outcome. |

| Tier | Domain task | DSA | Assistant |
| --- | --- | --- | --- |
| Novice | Localized bug fix or small feature | Easy | No |
| Adept | Multi-step feature across 2–3 files | Medium | Yes |
| Master | Multi-file debugging/extension with performance constraints | Medium/Hard | Yes |

Featherless is required for: portfolio analysis, task spec generation and
validation support, and powering the guarded assistant. We also use it for
the voice interviewer (text and speech).

## 2. Locked decisions

| Area | Decision | Why |
| --- | --- | --- |
| Assessment structure | One tier per assessment; domain task (~35 min) + DSA task (~25 min) | Assistant is tied to the tier |
| Default generation | Seed-based: a hand-written, tested seed repo is the reference; the starter is made by mutating or removing code | Reference is correct by construction |
| Second mode | LLM-written tasks through the same gate | Variety; shows the gate working |
| Personalization | Seeds tagged with concepts; portfolio highlights pick the target; LLM renames entities | Personal and reliable |
| DSA | Tagged bank; every tag must be claimed; solved-count thresholds per tier; problems rewritten into the candidate's domain | Topic boundary holds by construction |
| Difficulty | AI solve-rate probe (3 attempts, graded by tests); rejects tasks AI solves too easily | Comparability; blocks paste-into-AI tasks |
| Runtime | Docker runner, network off; all grading on the server | Isolation, tamper-proof |
| Hidden tests | Run silently on every Run (logged, never shown); fresh DSA inputs at Submit | Real progress signal; no hard-coding |
| LLM access | OpenAI SDK + Instructor → Featherless; slots: generator, assistant, probe, interviewer | Validated output; swappable models |
| Scoring | Novice 100% correctness; Adept/Master 80% correctness + 20% AI efficiency | Matches the PS |
| Reproducibility | Versioned tasks, stored seeds and snapshots, Re-grade button | Exact recomputation |
| Voice interviewer | Browser speech recognition + Featherless LLM + Featherless TTS; never scored | Free apart from Featherless; PS-compliant |
| Tokens | Project-wide token policy (see CLAUDE.md) | Don't waste Featherless usage |
| MVP scope | Python + JavaScript; Backend and Web polished; one seed each for ML, Security | Depth over breadth |

Non-negotiable rules are in CLAUDE.md.

## 3. Architecture

Services (one docker-compose): Next.js web app ↔ FastAPI backend (REST +
WebSocket) → PostgreSQL (tasks, sessions, events, scores) and Redis (job
queue, LLM/TTS cache) → Celery workers (build, gate, probe, run, grade) →
Docker runners (fresh container, network off). Backend and workers call
Featherless. Candidate code never runs in the backend process.

| # | Module | What it does |
| --- | --- | --- |
| 1 | Profiler | Portfolio → domain, runtime, concepts, allowed DSA topics per tier |
| 2 | Task builder | Seed mutation (Novice), feature removal (Adept), bug + perf regression (Master), LLM mode, DSA bank + rewriting |
| 3 | Validation gate | Reference ×3, starter fails, scope, size, trivial-stub test strength (DSA), statement leak check, perf calibration, topic check, optional mutation score → certificate |
| 4 | AI probe | Small model attempts each task 3 times, graded by tests → difficulty index |
| 5 | Runner | Visible tests on Run, hidden tests silently, everything on Submit |
| 6 | Web IDE | Monaco, tests panel, server timer, autosave, telemetry |
| 7 | Guarded assistant | Hint ladder L1–L3, input rules, similarity guard vs reference, code cap, rate limit |
| 8 | Scoring | Correctness, AI efficiency, difficulty-adjusted score, re-grade |
| 9 | Report | Certificate, metrics, claim map, hint ROI, Trail Map, integrity flags, interview tab |
| 10 | Simulated candidates | Scripted sessions for tuning and demo |
| 11 | Voice interviewer | See docs/INTERVIEWER.md |

Flow A (recruiter, background): upload portfolio, pick tier → profile →
build domain + DSA tasks → gate → probe → repair (≤2) or fallback bank →
candidate link.

Flow B (candidate, 60 min): server timer → Run (visible shown, hidden
logged) → hints (guarded) → Submit or deadline → full grade.

Flow C (after): optional voice interview → scoring from stored records only →
report.

## 4. Data contracts

Implemented in contracts/ (P0.2): portfolio (JSON Resume + `assessment.dsaTopicsSolved`),
task_spec, candidate_task_view, event, run_result. Event types: run, submit,
hint_request, hint_response, guard_block, focus, edit, paste, blur. New
schemas are added there first (e.g. profile, interview_plan).

## 5. Scoring

```text
correctness(task) = 100 × (0.3 × visible_f2p_rate + 0.7 × hidden_f2p_rate)
                        × regression_factor × perf_factor
    f2p_rate          = share of the fail_to_pass tests (fail on the starter, recorded by
                        the gate) that now pass; an untouched starter scores 0
    regression_factor = share of the pass_to_pass tests (pass on the starter) that still
                        pass; 1.0 if there are none
    a split with no fail_to_pass tests gives its weight to the other one
    DSA: every case counts as fail_to_pass (rates over all cases), regression_factor 1.0
    tasks stored without the ids: rates over all tests, regression_factor 1.0 (logged;
        the breakdown says rates_over = all_tests)
    perf_factor = 1.0 within budget, linear down to 0.5 at 3× budget (Master); 0.5 with a
        budget but no measurement

AI efficiency E (Adept/Master):
    PPH  = mean over hints: tests fixed within 5 min / tests failing at hint time
    TD   = share of hints preceded by ≥1 run since the previous hint
    FREQ = 1 if 1–6 runs per 10 min, tapering to 0 outside
    IND  = 1 − min(1, (L1×1 + L2×2 + L3×3) / 12)
    E    = clamp(0.35·PPH + 0.20·TD + 0.15·FREQ + 0.30·IND − 0.15·extraction_attempts, 0, 1)
    E    = E × min(1, mean_correctness / 50)
    zero hints → E = mean_correctness / 100

final: Novice = mean(correctness); Adept/Master = 0.8 × mean(correctness) + 20 × E
not scored: difficulty-adjusted score, Trail Map metrics, integrity flags, interview
bands: Strong ≥ 80, Pass ≥ 60, Borderline ≥ 45, Not yet < 45
```

Tune weights with the simulated candidates.

## 6. Novelty features

- **Debug Trail Map (headline):** replayable map of the seed repo (functions
  as nodes, call edges) with the candidate's navigation path, dwell time,
  hint moments, and hidden-test progress. Metrics: time to bug, off-path
  time, found independently vs after a hint, edit precision. Report-only.
- **AI voice interviewer:** company/role-specific audio interview that asks
  candidates to explain their own submission and portfolio (docs/INTERVIEWER.md).
- **Validation certificate** per task.
- **AI solve-rate probe** and difficulty index.
- **Live attack demo + promptfoo report** for the assistant.
- **Claim verification map**, **hint ROI chart**, **DSA domain rewriting**,
  **simulated candidates**, **Re-grade button**.
- Stretch: adaptive mode (IRT), GitHub-grounded tasks, code replay,
  outside-AI similarity flag, collusion detection.

## 7. Open-source resources

| Area | Resource | Use | License |
| --- | --- | --- | --- |
| Portfolio | JSON Resume schema | Base portfolio format | MIT |
| LLM | Featherless API | Text and speech | Service |
| LLM | Instructor | Validated structured output | MIT |
| Generation | SWE-smith (method) | Bug mutation, issue text | See repo |
| Generation | LibCST | Formatting-preserving code edits | MIT |
| DSA | LeetCodeDataset | Tagged problems + tests (never served verbatim) | Apache-2.0 |
| Validation | EvalPlus (method), mutmut, StrykerJS, Hypothesis, fast-check | Test strength, differential testing | See repos |
| Sandbox | llm-sandbox / Docker SDK | Runner | MIT / Apache-2.0 |
| Editor | Monaco + @monaco-editor/react; Sandpack (preview only) | IDE | MIT / Apache-2.0 |
| Guard | copydetect, LLM Guard (rules), promptfoo | Leak guard, attack testing | See repos / MIT |
| Trail Map | Python `ast` (stdlib; F4) and React Flow | Function spans, call graph; replay UI | PSF / MIT |
| Voice | Web Speech API (browser), faster-whisper (optional fallback), Three.js (orb) | Listening, orb | Browser / MIT |
| Security tasks | Bandit, Semgrep CE (own rules) | Static checks | Apache-2.0 / LGPL-2.1 |
| Stretch | catsim, Dolos | Adaptive mode, collusion | See repos / MIT |

Every dependency actually used goes in ATTRIBUTIONS.md.

## 8. Layout and seeds

See CLAUDE.md for the folder layout. Seeds (each 6–10 files, ≤500 lines of
app code, deterministic tests, concepts.yaml, README_TOUR.md):

| Seed | Domain | Runtime | Status |
| --- | --- | --- | --- |
| py-fastapi-expenses | Backend | Python | Done (P0.5) |
| node-express-orders | Backend | Node | To do |
| react-task-board | Web | Node + Jest | To do |
| py-flask-login | Security | Python | To do |
| py-sklearn-churn | ML | Python | To do |

## 9. Build plan

Phases (don't start one until the previous exit test passes):
0. Setup — done.
1. Walking skeleton — one hard-coded task solved, submitted, and scored in the browser.
2. Generation + gate — two portfolios produce two validated assessments with certificates.
3. Assistant + scoring — simulated candidates get clearly different AI scores; extraction blocked.
4. Report + Trail Map + interviewer — a real session's report shows all features.
5. Polish + demo — pre-generated data, backup video, two rehearsals. Feature freeze.

Team of 3: A Execution, B Generation + AI and scoring, C Frontend +
interviewer UI. Must-haves first: Python + JS, Backend + Web seeds, seed
mode + DSA bank, hint ladder + similarity guard, report with Trail Map.

## 10. Risks and demo

| Risk | Fallback |
| --- | --- |
| Featherless slow or limited | Pre-generate demo data; cache everything |
| Gate rejects too many tasks | Fallback bank; seed mode default |
| Flaky perf tests | Calibrate on demo machine; 3× multiplier |
| Browser speech recognition fails | Push-to-talk; optional faster-whisper |
| Integration breaks late | Keep the walking skeleton green; merge small and often |
| Live demo failure | Recorded backup video |

Demo (5 min): problem → two portfolios, two assessments → certificate and a
rejected task → live session with a blocked extraction attempt → report:
claim map, hint ROI, Trail Map (same score, different trails) → short voice
interview clip → Re-grade gives the same number.

## 11. Threat model

What a candidate (or their AI tools) might try against grading, and what stops it.
Code: backend/app/workspace.py, grading.py, integrity.py, backend/runner/.

| Attack | Defence |
| --- | --- |
| Edit or add tests, conftest.py, pytest.ini, package.json, jest/babel config, sitecustomize.py, .pth files | **Editable allowlist**: only starter files outside tests and test/package config can be edited. Enforced at save (422 with a reason per path), at Run, and again when the workspace is built (anything else is dropped and noted as `dropped_paths`) |
| Read hidden tests (print them, read them from disk) | **Separate hidden runs**: hidden tests run only in their own sandbox; the visible run never contains them. Hidden output, test names and messages are stored, never returned. DSA expected answers never enter any sandbox: the harness gets inputs only and the backend compares outputs (app/dsa.py) |
| Delete, rename or replace test files during a run | **Root-owned test files**: test and config files are root-owned 0444, and every directory above them (the workspace root included) is root-owned 0755, so the sandbox user can't modify, delete, rename or add files there |
| Skip, add or rename tests to change pass counts | **Test-ID check**: the collected test ids must equal the ids recorded when the task was built (`visible_test_ids` / `hidden_test_ids`); otherwise status error, reason `test_set_mismatch`, zero passes |
| Pre-write or overwrite the JSON report | **Random report path**: report and exit code go to a separate volume outside /workspace under a random name per run |
| Interfere with pytest, the interpreter or the file system from candidate code | **Suspicious-code flags**: `_pytest`, `sys.modules`, `os._exit`, module-level exit, builtins patching, importlib tricks, writes outside /workspace are flagged on the run (`runs.integrity`) for the recruiter. Never blocks, never scored |
| Escape the sandbox, use the network, exhaust resources | Runner container: network off, read-only root file system, non-root user, no capabilities, CPU/memory/PID/time limits, fresh container per run |
| Many parallel Runs to probe hidden tests | One run per session at a time (429); hidden results only ever leave as counts in the run event, which the candidate never sees |

**Known limitation.** Candidate code is imported into the pytest process, so it can
still tamper with pytest at run time (e.g. patch the reporter, or find the report path
in `sys.argv` and overwrite the report). This is detected, not prevented: a forged
report with a different test set fails the test-ID check, and writes outside /workspace
and pytest internals are flagged. A forged report that keeps the exact test ids but flips
outcomes is not caught automatically; the flags make it visible in the report. Closing
this fully would mean reporting from outside the test process (e.g. per-test
subprocesses), which costs run time.

