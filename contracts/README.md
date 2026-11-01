# contracts

JSON Schemas (draft 2020-12) shared by the backend and frontend. **These files are the source of truth.**

| Schema | What it describes |
| :--- | :--- |
| `portfolio.schema.json` | Candidate portfolio: JSON Resume plus a required `assessment` extension. Project `keywords` are the tech stack. |
| `task_spec.schema.json` | Full task specification. Backend only. |
| `candidate_task_view.schema.json` | The part of a task the browser may see. No reference, hidden tests, hidden DSA cases or certificate. |
| `event.schema.json` | One session event; `type` selects the payload shape. |
| `run_result.schema.json` | Result of one sandboxed test run. |

## Changing a schema

1. Edit the `.schema.json` file.
2. Run `make contracts`. It regenerates:
   - Pydantic v2 models in `backend/contracts_gen/` (datamodel-code-generator)
   - TypeScript types in `frontend/lib/contracts/` (json-schema-to-typescript)
3. Update the fixtures in `fixtures/` and any backend and frontend code that uses the schema, in the same change.
4. Run `make test` and commit the schema, the fixtures and the generated files together.

Never edit generated files by hand. In the frontend, import root types from `@/lib/types`.

## Fixtures

`fixtures/<schema>.valid*.json` must pass and `fixtures/<schema>.invalid.json` must fail, both against the JSON Schema and the generated Pydantic model (`backend/tests/test_contracts.py`). Each invalid fixture has exactly one defect, and the test checks that it fails for that reason.

## Generator limitation

`FileMap.propertyNames` repeats the `RelPath` pattern instead of using `$ref`, because datamodel-code-generator emits broken Python for a `$ref` there. Edit both together; a test fails if they differ.
