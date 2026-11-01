# dsa

The DSA problem bank. Backend only: mounted read-only at `/dsa` in the api and worker
containers, never into a sandbox. One folder per problem:

| File | What it is |
| :--- | :--- |
| `problem.json` | Metadata (`builder.dsa_bank.BankProblem`): id, difficulty, tiers, canonical tags, entry point, typed signature, comparator, source |
| `problem.md` | Statement with the bank's names: our own words (`own_statement: true`) or a template built by code. Tasks get a domain rewrite instead (`builder/dsa_rewrite.py`) |
| `stub.py` | Starter `solution.py` with the bank's names (tasks generate the starter for their runtime and names) |
| `reference.py` | Reference solution, entry point = `entry_point`. Re-checked in the sandbox (renamed) whenever a task is built |
| `cases.json` | `{"visible": [5 cases], "hidden": [pool]}`, each `{"id", "input", "expected"}`; inputs are keyword arguments |
| `make_cases.py` | Hand-written problems only: regenerates `cases.json` |

Problems: `longest_unique_substring` (hand-written for P1.3) and ~100 imported from
LeetCodeDataset by `make dsa-import` (`tools/import_leetcode.py`, pinned revision; see
ATTRIBUTIONS.md). The import keeps only JSON-typed signatures whose tags all map to
`taxonomy.yaml`, parses cases with `ast` (never exec/eval), and recomputes every expected
value by running the reference in the sandbox. Easy -> novice, Medium -> adept + master,
Hard -> master, minus tiers a topic isn't allowed in.

`raw/` (git-ignored, `make lint` fails if anything in it is tracked): the downloaded
dataset and the original descriptions (`raw/descriptions/<id>.md`), LeetCode's text, used
only as rewrite input. Without it, tasks use the template statement.

Grading (`backend/app/dsa.py`): the sandbox gets only `{id, input}` pairs and a harness
(`backend/runner/harness/python_cases.py`, `node_cases.js`) that calls the candidate's
function with a per-case timeout; the backend compares outputs with `expected` (exact by
default, or the comparator). Each session is graded on up to 30 hidden cases sampled from
the pool (seeded by session and task); the submit stores the seed and the ids.
