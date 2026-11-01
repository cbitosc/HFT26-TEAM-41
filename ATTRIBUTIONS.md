# Attributions

Open-source libraries, datasets, models and borrowed methods used in this project.
Add every new one here in the same change that introduces it (CLAUDE.md).

## Used as dependencies

### Backend (Python, `backend/pyproject.toml`)

| Library | License | Use |
| :--- | :--- | :--- |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | HTTP API |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI server |
| [Pydantic](https://github.com/pydantic/pydantic) / [pydantic-settings](https://github.com/pydantic/pydantic-settings) | MIT | Data models, env config |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | MIT | Database access |
| [Alembic](https://github.com/sqlalchemy/alembic) | MIT | Database migrations |
| [psycopg](https://github.com/psycopg/psycopg) | LGPL-3.0 | PostgreSQL driver |
| [redis-py](https://github.com/redis/redis-py) | MIT | Redis client |
| [Celery](https://github.com/celery/celery) | BSD-3-Clause | Background task queue |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | Apache-2.0 | Client for Featherless's OpenAI-compatible API |
| [Instructor](https://github.com/567-labs/instructor) | MIT | Structured (JSON mode) LLM output with validation retries |
| [Docker SDK for Python](https://github.com/docker/docker-py) | Apache-2.0 | Starting sandbox containers in backend/runner |
| [Hatchling](https://github.com/pypa/hatch) | MIT | Python build backend |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Tests (dev) |
| [httpx2](https://github.com/pydantic/httpx2) | BSD-3-Clause | HTTP client for FastAPI's TestClient (dev) |
| [Ruff](https://github.com/astral-sh/ruff) | MIT | Lint and format (dev) |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | MIT | Validating contract fixtures in tests (dev) |
| [datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator) | MIT | Generating Pydantic models from contracts/ (dev) |
| [fakeredis](https://github.com/cunla/fakeredis-py) | BSD-3-Clause | In-memory Redis for LLM client tests (dev) |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | Reading dsa/taxonomy.yaml and seed concepts.yaml files (profiler, tests) |
| [LibCST](https://github.com/Instagram/LibCST) | MIT | Formatting-preserving code edits in the task builders: bug mutation (`builder/mutate.py`), feature removal (`builder/remove_feature.py`) |
| [copydetect](https://github.com/blingenf/copydetect) 0.5.0 (pulls in NumPy, Matplotlib, Jinja2, Pygments, tqdm) | MIT | Hint assistant output guard: winnowing similarity of reply code to the reference side of the fix (`assistant/guards.py`, F2) |

### Frontend (TypeScript, `frontend/package.json`)

| Library | License | Use |
| :--- | :--- | :--- |
| [Next.js](https://github.com/vercel/next.js) / create-next-app | MIT | App framework and scaffold |
| [React](https://github.com/facebook/react) / React DOM | MIT | UI |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) / @tailwindcss/turbopack | MIT | Styling |
| [TypeScript](https://github.com/microsoft/TypeScript) | Apache-2.0 | Type checking |
| [DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped) (@types/node, @types/react, @types/react-dom) | MIT | Type definitions |
| [ESLint](https://github.com/eslint/eslint) / eslint-config-next | MIT | Lint |
| [json-schema-to-typescript](https://github.com/bcherny/json-schema-to-typescript) | MIT | Generating TypeScript types from contracts/ |
| [Monaco Editor](https://github.com/microsoft/monaco-editor) / [@monaco-editor/react](https://github.com/suren-atoyan/monaco-react) | MIT | Candidate IDE editor (P1.4). monaco-editor 0.55.1 is bundled from npm (core editor + a few syntax highlighters, lib/monaco.ts), no CDN (P1.4b) |
| [react-markdown](https://github.com/remarkjs/react-markdown) | MIT | Rendering task statements and repo tours (P1.4) |
| [Recharts](https://github.com/recharts/recharts) 3.10.1 | MIT | Report charts: hidden-test progress timeline, AI efficiency parts (F3) |
| [shadcn/ui](https://github.com/shadcn-ui/ui) (Card, Badge, Tabs copied into `components/ui/`, recoloured with plain Tailwind) | MIT | Report layout (F3) |
| [Radix UI Tabs](https://github.com/radix-ui/primitives) (@radix-ui/react-tabs 1.2.1) | MIT | Tabs primitive under the shadcn/ui Tabs |
| [class-variance-authority](https://github.com/joe-bell/cva) 0.7.1, [clsx](https://github.com/lukeed/clsx) 2.1.1, [tailwind-merge](https://github.com/dcastil/tailwind-merge) 3.7.0 | Apache-2.0 / MIT / MIT | shadcn/ui's variants and `cn` class helper (`lib/utils.ts`) |
| [React Flow](https://github.com/xyflow/xyflow) (@xyflow/react 12.12.0) | MIT | Trail Map tab on the report: function graph grouped by file, animated trail (F4) |
| [assistant-ui](https://github.com/assistant-ui/assistant-ui) (@assistant-ui/react 0.15.29) | MIT | Hint assistant chat panel in the IDE: thread, messages and composer primitives over our hint API (F2) |
| [GSAP](https://github.com/greensock/GSAP) 3.15.0 (ScrollTrigger, SplitText) | GSAP Standard License (free, no-charge) | Scroll, text and page-transition animation in the themed journey (`components/olympus`) |
| [Lenis](https://github.com/darkroomengineering/lenis) 1.3.27 | MIT | Smooth scrolling on the landing, Offering and Verdict pages |
| [Fontsource](https://github.com/fontsource/fontsource): Cormorant Garamond, Inter Tight, JetBrains Mono (variable) 5.3.0 | Fonts: SIL OFL 1.1; packaging: MIT | Self-hosted fonts for the themed pages (no font CDN) |

### Showcase site (`showcase/package.json`)

A standalone static site for the project presentation. Versions are pinned exactly.

| Library | License | Use |
| :--- | :--- | :--- |
| [Next.js](https://github.com/vercel/next.js) 16.4.3 | MIT | App framework, static export |
| [React](https://github.com/facebook/react) / React DOM 19.3.0 | MIT | UI |
| [TypeScript](https://github.com/microsoft/TypeScript) 5.9.3 | Apache-2.0 | Type checking |
| [DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped) (@types/node, @types/react, @types/react-dom) | MIT | Type definitions |
| [Motion](https://github.com/motiondivision/motion) 14.3.0 | MIT | Scroll-linked and reveal animations |
| [Lenis](https://github.com/darkroomengineering/lenis) 1.3.26 | MIT | Smooth scrolling |
| [Fontsource](https://github.com/fontsource/fontsource) (@fontsource-variable/cormorant, cinzel, eb-garamond, archivo, jetbrains-mono 5.3.0) | MIT (packaging) | Self-hosted font files, no font CDN |
| [Cormorant](https://github.com/CatharsisFonts/Cormorant) (Christian Thalmann) | OFL-1.1 | Display typeface |
| [Cinzel](https://github.com/NDISCOVER/Cinzel) (Natanael Gama) | OFL-1.1 | Inscriptions: labels, small capitals |
| [EB Garamond](https://github.com/octaviopardo/EBGaramond12) (Georg Duffner, Octavio Pardo) | OFL-1.1 | Greek letters (numerals, the Delphi motto), which Cormorant lacks |
| [Archivo](https://github.com/Omnibus-Type/Archivo) (Omnibus-Type) | OFL-1.1 | Text typeface |
| [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) | OFL-1.1 | Code typeface |
| Blue engraving asset sheets (Greek and Roman figures, architecture, ornaments) | Provided by the team (source to be confirmed) | `showcase/public/greek/`: single engravings cut from the sheets by `showcase/scripts/cut-greek.mjs` (sharp, already a Next.js dependency) |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (Xintao Wang et al.), lightweight anime x4 weights from [xiongjie/lightweight-real-ESRGAN-anime](https://huggingface.co/xiongjie/lightweight-real-ESRGAN-anime) | BSD-3-Clause | Build-time only: `showcase/scripts/upscale-sheets.py` upscales the asset sheets 4x; 35% of each cut engraving comes from it (crisp outlines), the rest from sharpened Lanczos (keeps the stipple) |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime), [NumPy](https://github.com/numpy/numpy), [Pillow](https://github.com/python-pillow/Pillow) | MIT, BSD-3-Clause, MIT-CMU | Build-time only: run the upscaler (`uv run --with ...`), not shipped |
| [Hermes Agent](https://hermes-agent.nousresearch.com/) site (Nous Research) | Design reference only | Inspiration for pairing classical engraving with a technical product; no code or assets used |

Product screenshots on the site are captured from our own running app with Playwright (listed under End-to-end test).

The `/interview` practice demo uses only browser APIs: the [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) (speech recognition and the built-in speech synthesis voice) and the [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API) (mic level for the blob). No new packages.

### Code reading app (`code-compr/package.json`)

| Project | License | Use |
| :--- | :--- | :--- |
| [Prisma](https://github.com/prisma/prisma), [Next.js](https://github.com/vercel/next.js) | Apache-2.0 / MIT | code-compr/ |

### Archived: coding-assessment (branch `archive/coding-assessment`, not on main)

| Project | License | Use |
| :--- | :--- | :--- |
| [Judge0](https://github.com/judge0/judge0) | GPL-3.0 | Code execution service for coding-assessment/ (used over HTTP, not bundled) |
| [Express](https://github.com/expressjs/express), [helmet](https://github.com/helmetjs/helmet), [express-rate-limit](https://github.com/express-rate-limit/express-rate-limit), [cors](https://github.com/expressjs/cors) | MIT | coding-assessment/ API |
| [BullMQ](https://github.com/taskforcesh/bullmq), [ioredis](https://github.com/redis/ioredis) | MIT | coding-assessment/ job queue |
| [Mongoose](https://github.com/Automattic/mongoose) | MIT | coding-assessment/ MongoDB models |
| [Anthropic TypeScript SDK](https://github.com/anthropics/anthropic-sdk-typescript) | MIT | coding-assessment/ debug hints and challenge generation |
| [axios](https://github.com/axios/axios), [dotenv](https://github.com/motdotla/dotenv) | MIT | coding-assessment/ |
| [React](https://github.com/facebook/react), [react-router](https://github.com/remix-run/react-router), [react-markdown](https://github.com/remarkjs/react-markdown), [Vite](https://github.com/vitejs/vite) | MIT | coding-assessment/ frontend |

### Runner images (`runtimes/`)

| Software | License | Use |
| :--- | :--- | :--- |
| [Python](https://www.python.org/) (`python:3.11.18-slim`) | PSF-2.0 | Python runtime image base |
| [Node.js](https://nodejs.org/) (`node:20.20.2-slim`) | MIT | Node runtime image base |
| [pytest-json-report](https://github.com/numirias/pytest-json-report) | MIT | Machine-readable pytest results |
| [pytest-timeout](https://github.com/pytest-dev/pytest-timeout) | MIT | Per-test timeouts available to task authors |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | MPL-2.0 | Property-based tests |
| [mutmut](https://github.com/boxed/mutmut) 2.5.1 | BSD-3-Clause | Optional mutation score of a task's hidden tests on the reference (`backend/gate/mutation.py`, `make gate MUTATION=1`) |
| [HTTPX](https://github.com/encode/httpx) | BSD-3-Clause | HTTP client for FastAPI test clients in tasks |
| [Jest](https://github.com/jestjs/jest) | MIT | JavaScript test runner |

pytest, FastAPI, SQLAlchemy and Pydantic are also installed in the Python image (listed above).

### Infrastructure (`docker-compose.yml`, Dockerfiles)

| Software | License | Use |
| :--- | :--- | :--- |
| [PostgreSQL 16](https://www.postgresql.org/) (Docker image) | PostgreSQL License | Database |
| [Redis 7](https://github.com/redis/redis) (Docker image) | BSD-3-Clause | Broker, result backend, LLM cache |
| [Python](https://www.python.org/) (`python:3.11-slim`) | PSF-2.0 | API and worker image base |
| [Node.js](https://nodejs.org/) (`node:24-slim`) | MIT | Frontend image base |

### End-to-end test (`e2e/`)

| Software | License | Use |
| :--- | :--- | :--- |
| [Playwright](https://github.com/microsoft/playwright) 1.64.1 (npm package and `mcr.microsoft.com/playwright:v1.64.1-noble` image with Chromium) | Apache-2.0 | `make e2e`: headless-browser run of the demo flow |

### Datasets

| Dataset | License | Use |
| :--- | :--- | :--- |
| [LeetCodeDataset](https://github.com/newfacade/LeetCodeDataset) ([Hugging Face copy](https://huggingface.co/datasets/newfacade/LeetCodeDataset), revision `215604aeed660029df7de2fea5a4d7b6ed476a08`) | Apache-2.0 | `make dsa-import` (P2.6): tags, signatures, test inputs and reference solutions for the ~100 problems in `dsa/`. Expected values recomputed in our sandbox. The original problem descriptions are LeetCode's text: kept only in the git-ignored `dsa/raw/` as rewrite input, never committed or served |

### Models and services (via Featherless)

| Model / service | License | Use |
| :--- | :--- | :--- |
| [Featherless API](https://featherless.ai/) | Service | All LLM calls (and, from P4.9, speech) |
| [DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai) (-0731 build) | See model card | Generator and assistant slots |
| [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | Apache-2.0 | Probe slot (480B variant for final calibration) |
| [Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | Apache-2.0 | Interviewer slot (provisional until P4.9) |

## Methods we adapted

| Source | License | Use |
| :--- | :--- | :--- |
| [JSON Resume schema](https://github.com/jsonresume/resume-schema) | MIT | `contracts/portfolio.schema.json` follows its `basics`, `skills`, `projects` and `meta` structure and its ISO 8601 date pattern |
| [LeetCode 3, "Longest Substring Without Repeating Characters"](https://leetcode.com/problems/longest-substring-without-repeating-characters/) | Problem idea only | `dsa/longest_unique_substring`: the classic sliding-window problem. Statement, stub, reference solution and all cases written by us; no LeetCode text or tests used |
| [DeepInterview](https://github.com/ngoanpv/DeepInterview) | Apache-2.0 (method only) | `showcase/components/interview/`: the live interview flow (setup, stage + transcript + timer + typed fallback, then notes), sectioned question plans with follow-ups, the word-count difficulty signal (`evaluate_difficulty`, thin answer < 12 words) and the hard time/turn ceilings (`SessionGuard`). Rewritten for the browser; no DeepInterview code, LiveKit or paid voice services used |
| [SWE-smith](https://github.com/SWE-bench/SWE-smith) | MIT (method only) | `backend/builder/mutate.py`: the idea of injecting bugs into a working repo procedurally and keeping only those that break some of its tests. Operators and the filter are our own code; no SWE-smith code or data used. Issue-text generation (P2.5) not used yet |

## Planned

From docs/BLUEPRINT.md section 7. Move a row up to "Used as dependencies" or
"Methods we adapted" when it is actually used.

| Resource | License | Planned use |
| :--- | :--- | :--- |
| [EvalPlus](https://github.com/evalplus/evalplus) (method) | Apache-2.0 | Test strengthening, differential testing (P2.7) |
| [StrykerJS](https://github.com/stryker-mutator/stryker-js) | Apache-2.0 | Mutation score, JavaScript (P2.7) |
| [fast-check](https://github.com/dubzzz/fast-check) | MIT | Property-based tests, JavaScript (P2.7) |
| [llm-sandbox](https://github.com/vndee/llm-sandbox) | MIT | Alternative runner backend |
| [Sandpack](https://github.com/codesandbox/sandpack) | Apache-2.0 | Web preview only |
| [LLM Guard](https://github.com/protectai/llm-guard) (rules) | MIT | Assistant input rules (P3.2) |
| [promptfoo](https://github.com/promptfoo/promptfoo) | MIT | Attack testing of the assistant (P3.6) |
| [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) | Browser API | Interviewer listening (P4.9) |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (via Featherless) | Apache-2.0 | Interviewer voice (P4.9) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Optional speech-recognition fallback (P4.12) |
| [Three.js](https://github.com/mrdoob/three.js) | MIT | Interviewer orb (P4.10) |
| [Bandit](https://github.com/PyCQA/bandit) | Apache-2.0 | Static checks for security tasks |
| [Semgrep CE](https://github.com/semgrep/semgrep) (own rules) | LGPL-2.1 | Static checks for security tasks |
| [catsim](https://github.com/douglasrizzo/catsim) | See repo | Stretch: adaptive mode (IRT) |
| [Dolos](https://github.com/dodona-edu/dolos) | MIT | Stretch: collusion detection |

## Borrowed methods and artwork (frontend theme)

| Source | License | Use |
| :--- | :--- | :--- |
| [webgl-noise](https://github.com/ashima/webgl-noise) 3D simplex noise (Ashima Arts, Stefan Gustavson) | MIT | GLSL noise in the Oracle's orb shader (`components/olympus/OracleOrb.tsx`) |
| Greek engraving sheets supplied by the team | Team-provided | Cut into `frontend/public/engravings/*.webp` masks by `frontend/scripts/extract-engravings.py` |
