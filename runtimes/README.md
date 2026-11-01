# runtimes

One Docker image per runtime. `backend/runner` starts a fresh container from one of these for every test run. Build them with `make runtimes`.

| Runtime id | Image | Contents |
| :--- | :--- | :--- |
| `python311` | `assess-python311` | Python 3.11.18, pytest, pytest-json-report, pytest-timeout, hypothesis, fastapi, httpx, sqlalchemy, pydantic |
| `node20` | `assess-node20` | Node 20.20.2, Jest 30 preinstalled from a lockfile in `/opt/jest` (on `PATH`, and on `NODE_PATH` for `require`) |

The runtime id is what `TaskSpec.runtime` holds and what `run_tests(runtime, ...)` takes.

## Sandbox settings (set by the runner, not the image)

- No network (`network_mode: none`)
- 512 MB memory with no swap, 1 CPU, at most 128 processes
- Read-only root filesystem; the only writable path is `/workspace`, a 64 MB in-memory volume
- Runs as uid 10001 (`runner`), all capabilities dropped, `no-new-privileges`
- Container logs capped at 1 MB; the result keeps the last 4 KB of stdout and stderr

## Pinning

- Python: `requirements.txt` lists the direct dependencies; `constraints.txt` pins every package (a `pip freeze` of the installed image). Regenerate it when bumping a version.
- Node: `jest/package-lock.json` pins Jest and its dependencies.
- Base images are pinned to exact patch tags.

Node 20 reached end of life in April 2026. Plan to move to Node 22 or 24.
