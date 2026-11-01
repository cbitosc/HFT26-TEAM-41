.PHONY: up down migrate seed-demo e2e test test-docker lint contracts runtimes mutate remove-feature build-master enrich gate llm-smoke llm-usage dsa-import

up:
	docker compose up -d --build

down:
	docker compose down

# Apply database migrations (backend/migrations) to the dev database.
migrate:
	docker compose run --rm api alembic upgrade head

# Build and validate the P1.3 demo tasks in the sandbox, store an assessment, start its
# session and print the URL. Runs in the worker (it needs the Docker socket).
seed-demo:
	docker compose run --rm worker sh -c "alembic upgrade head && python -m builder.seed_demo --tier $(or $(TIER),novice)"

# Headless-browser run of the demo against the running stack (`make up` first). Restarts
# worker and beat so they run the current code, then: a fresh seed-demo session, fix both tasks in the bundled Monaco, Run, Submit, open the report
# and assert the scores. Any request leaving the stack fails it. ~2 min.
e2e:
	./e2e/run.sh

# Practice mode (/practice): list, Run, custom input, Submit in Python and JavaScript. ~30 s.
e2e-practice:
	./e2e/practice.sh

# Starts postgres/redis if needed; the health test hits the real services. API tests
# build their own <db>_test database from the migrations, never touching dev data.
test:
	docker compose run --rm api pytest

# Runner tests that start real sandbox containers. Needs `make runtimes` first. Runs in the
# worker, the only service with the Docker socket.
test-docker:
	docker compose run --rm worker pytest -m docker --durations=0

lint:
	@test -z "$$(git ls-files dsa/raw)" || { echo "dsa/raw/ holds LeetCode's text and must never be committed:"; git ls-files dsa/raw; exit 1; }
	docker compose run --rm --no-deps api ruff check . /seeds
	docker compose run --rm --no-deps api ruff format --check . /seeds
	docker compose run --rm --no-deps frontend npm run lint

# Regenerate types from contracts/*.schema.json. Commit the output. Runs as the host user
# so the generated files aren't root-owned.
contracts:
	docker compose run --rm --no-deps --user "$$(id -u):$$(id -g)" api python scripts/generate_contracts.py
	docker compose run --rm --no-deps --user "$$(id -u):$$(id -g)" frontend npm run --silent contracts

# Sandbox images used by backend/runner.
runtimes:
	docker build -t assess-python311 runtimes/python311
	docker build -t assess-node20 runtimes/node20

# Mutation engine (P2.2): list a seed concept's bug candidates, pre-filter them in the sandbox
# and build a draft Novice task from the best one. Runs in the worker (Docker socket).
# Usage: make mutate SEED=py-fastapi-expenses CONCEPT=pagination [RNG_SEED=0]
RNG_SEED ?= 0
mutate:
	docker compose run --rm worker python -m builder.mutate $(SEED) $(CONCEPT) --rng-seed $(RNG_SEED)

# Feature removal (P2.3): stub a seed concept's code across 2-3 files, check it in the sandbox
# and print a validated draft Adept task. Without CONCEPT, lists which concepts are eligible.
# Usage: make remove-feature SEED=py-fastapi-expenses [CONCEPT=reporting]
remove-feature:
	docker compose run --rm worker python -m builder.remove_feature $(SEED) $(CONCEPT)

# Master builder (P2.4): one bug + one perf regression in different files, perf budget calibrated
# in the sandbox (3 x the reference's median over 5 runs). Prints the task and calibration.
# Usage: make build-master SEED=py-fastapi-expenses [CONCEPTS="pagination validation"] [RNG_SEED=0]
build-master:
	docker compose run --rm worker python -m builder.master $(SEED) $(CONCEPTS) --rng-seed $(RNG_SEED)

# LLM enrichment (P2.5): build a draft Novice or Adept task, then write its statement (one
# generator call, cached), copy the repo tour and rename domain entities when the re-run in the
# sandbox matches. Spends Featherless credits on a cache miss.
# Usage: make enrich SEED=py-fastapi-expenses TIER=novice|adept [CONCEPT=...] [PORTFOLIO=...]
enrich:
	docker compose run --rm worker python -m builder.enrich $(SEED) --tier $(TIER) $(if $(CONCEPT),--concept $(CONCEPT)) $(if $(PORTFOLIO),--portfolio $(PORTFOLIO))

# Validation gate (P2.7): re-check the newest stored task with this id in the sandbox and print
# its certificate, or the reasons it is rejected (exit 1). MUTATION=1 adds mutmut (1-3 min).
# Usage: make gate TASK=expenses-pagination [MUTATION=1]
gate:
	docker compose run --rm worker python -m gate $(TASK) $(if $(MUTATION),--mutation)

# One small real request per model slot. Spends Featherless credits on a cache miss.
llm-smoke:
	docker compose run --rm api python -m llm.smoke

# Tokens and estimated spend per slot.
llm-usage:
	docker compose run --rm api python -m llm.usage

# Import LeetCodeDataset (pinned revision) into the DSA bank: filters, runs every reference in
# the sandbox, writes dsa/<id>/. Original descriptions go to the git-ignored dsa/raw/. ~5 min.
dsa-import:
	docker compose run --rm -v "$$PWD/dsa:/dsa-out" -e PYTHONPATH=/app worker python /dsa-out/tools/import_leetcode.py --out /dsa-out
