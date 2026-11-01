"""Run tests on candidate code in a fresh, locked-down container (CLAUDE.md rule 3).

Lifecycle of one run:
1. Create two tmpfs-backed volumes (size-capped, in RAM): /workspace for the files, and
   /runner-out for the report and exit code, outside the workspace and under random
   names per run. The root filesystem is read-only, and Docker can't copy files into a
   plain --tmpfs mount, so these are volumes instead.
2. Start the container. Its launcher waits for /workspace/.runner/go.
3. Copy the files in, then create the go file. `readonly` files are owned by root with
   mode 0444, and so is every directory above them, the workspace root included, with
   mode 0755: the sandbox user can't edit, delete, rename or add files there. The
   launcher runs the test command and writes its exit code to /runner-out.
4. Poll for the exit code until the deadline. Read the report while the container is
   still running (a tmpfs volume is emptied once the container stops).
5. Always remove the container and the volumes.
"""

import io
import json
import logging
import tarfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container
from docker.types import LogConfig
from pydantic import ValidationError

from contracts_gen.run_result import RunResult, Summary, TestResult
from contracts_gen.task_spec import RelPath
from runner.runtimes import OUT_DIR, RUNTIMES, WORKSPACE

logger = logging.getLogger("runner")

RUNNER_UID = 10001  # the `runner` user in every runtimes/* image
MEMORY_LIMIT = "512m"
NANO_CPUS = 1_000_000_000  # 1 CPU
PIDS_LIMIT = 128
WORKSPACE_SIZE = "64m"
LOG_MAX_SIZE = "1m"  # caps container log storage; we only keep the tail anyway
TAIL_BYTES = 4096
POLL_INTERVAL_S = 0.1

OUT_SIZE = "8m"

RESERVED_DIR = ".runner"


def _launcher(exit_code_path: str) -> str:
    return (
        f"while [ ! -e {WORKSPACE}/{RESERVED_DIR}/go ]; do sleep 0.05; done; "
        f'"$@"; echo $? > {exit_code_path}; '
        # Stay alive so the report can be read before the tmpfs volume goes away.
        "exec sleep 3600"
    )


class RunnerError(RuntimeError):
    """The sandbox itself failed (Docker unavailable, image missing). Not the candidate's fault."""


@dataclass(frozen=True)
class ProgramRun:
    """Raw outcome of one sandboxed command. `report` is the JSON it wrote to report_path."""

    status: Literal["ok", "timeout", "oom", "error"]
    """ok: exited on its own. error: the launcher died without an exit code."""
    exit_code: int | None
    report: dict[str, Any] | None
    duration_ms: int
    stdout_tail: str
    stderr_tail: str


def run_program(
    runtime: str,
    files: dict[str, str],
    command: Callable[[str], list[str]],
    timeout_s: int = 30,
    readonly: frozenset[str] = frozenset(),
) -> ProgramRun:
    """Run `command(report_path)` in a fresh sandbox holding `files`.

    The report path is random per run and outside /workspace. `readonly` paths and their
    directories are root-owned.
    """
    spec = RUNTIMES.get(runtime)
    if spec is None:
        raise ValueError(f"Unknown runtime {runtime!r}; expected one of {sorted(RUNTIMES)}")
    _validate_paths(files)

    client = _docker_client()
    # The workspace root is above every readonly file, so it is root-owned too when there are any.
    root_owner = 0 if readonly else RUNNER_UID
    volumes = [
        _tmpfs_volume(client, "run", WORKSPACE_SIZE, owner=root_owner),
        _tmpfs_volume(client, "out", OUT_SIZE),
    ]
    workspace_volume, out_volume = volumes
    # Random per run and outside /workspace, so candidate code can't find or pre-write them.
    run_key = uuid.uuid4().hex
    report_path = f"{OUT_DIR}/{run_key}.json"
    exit_code_path = f"{OUT_DIR}/{run_key}.exit"
    container: Container | None = None
    try:
        try:
            container = client.containers.create(
                image=spec.image,
                command=["sh", "-c", _launcher(exit_code_path), "launcher", *command(report_path)],
                user=f"{RUNNER_UID}:{RUNNER_UID}",
                working_dir=WORKSPACE,
                environment={
                    "HOME": f"{WORKSPACE}/{RESERVED_DIR}/home",
                    "TMPDIR": f"{WORKSPACE}/{RESERVED_DIR}/tmp",
                },
                network_mode="none",
                mem_limit=MEMORY_LIMIT,
                memswap_limit=MEMORY_LIMIT,  # no swap
                nano_cpus=NANO_CPUS,
                pids_limit=PIDS_LIMIT,
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                init=True,
                volumes={
                    workspace_volume.name: {"bind": WORKSPACE, "mode": "rw"},
                    out_volume.name: {"bind": OUT_DIR, "mode": "rw"},
                },
                log_config=LogConfig(
                    type=LogConfig.types.JSON, config={"max-size": LOG_MAX_SIZE, "max-file": "1"}
                ),
                labels={"assess.runner": "sandbox", "assess.runtime": runtime},
            )
        except ImageNotFound as exc:
            raise RunnerError(f"Image {spec.image} not found; run `make runtimes`") from exc

        container.start()
        container.put_archive(WORKSPACE, _tar(files, readonly))
        container.put_archive(WORKSPACE, _tar({f"{RESERVED_DIR}/go": ""}))
        started = time.monotonic()

        exit_code, timed_out = _wait_for_exit_code(container, exit_code_path, started + timeout_s)
        duration_ms = round((time.monotonic() - started) * 1000)
        report = None if timed_out else _read_json(container, report_path)
        if timed_out:
            container.kill()
        container.reload()
        oom_killed = bool(container.attrs["State"].get("OOMKilled"))
        stdout = container.logs(stdout=True, stderr=False)
        stderr = container.logs(stdout=False, stderr=True)
    except DockerException as exc:
        raise RunnerError(f"Sandbox failure: {exc}") from exc
    finally:
        _cleanup(container, volumes)

    if timed_out:
        status = "timeout"
    elif oom_killed:
        status = "oom"
    elif exit_code is None:
        status = "error"
    else:
        status = "ok"
    return ProgramRun(
        status=status,
        exit_code=exit_code,
        report=report,
        duration_ms=duration_ms,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
    )


def run_tests(
    runtime: str,
    files: dict[str, str],
    test_paths: list[str],
    timeout_s: int = 30,
    readonly: frozenset[str] = frozenset(),
) -> RunResult:
    """Run `test_paths` against `files`. `readonly` paths and their directories are root-owned."""
    spec = RUNTIMES.get(runtime)
    if spec is None:
        raise ValueError(f"Unknown runtime {runtime!r}; expected one of {sorted(RUNTIMES)}")
    _validate_test_paths(test_paths)
    _validate_paths(dict.fromkeys(test_paths, ""))

    run = run_program(
        runtime,
        files,
        lambda report_path: spec.test_command(test_paths, set(files), report_path),
        timeout_s=timeout_s,
        readonly=readonly,
    )
    report = run.report
    tests = spec.parse_report(report) if report is not None else []
    status = run.status
    if status == "ok" and (report is None or not spec.ran_cleanly(run.exit_code, report)):
        status = "error"

    result = RunResult(
        status=status,
        reason=None,
        duration_ms=run.duration_ms,
        tests=tests,
        summary=_summarize(tests),
        stdout_tail=run.stdout_tail,
        stderr_tail=run.stderr_tail,
    )
    logger.info(
        json.dumps(
            {
                "event": "run",
                "runtime": runtime,
                "status": status,
                "exit_code": run.exit_code,
                "duration_ms": run.duration_ms,
                **result.summary.model_dump(),
            }
        )
    )
    return result


@lru_cache
def _docker_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except DockerException as exc:
        raise RunnerError(f"Docker is not reachable: {exc}") from exc


def _validate_paths(files: dict[str, str]) -> None:
    for path in files:
        try:
            RelPath.model_validate(path)
        except ValidationError as exc:
            raise ValueError(f"Invalid path {path!r}: must be a relative POSIX path") from exc
        if path.split("/")[0] == RESERVED_DIR:
            raise ValueError(f"Invalid path {path!r}: {RESERVED_DIR}/ is reserved for the runner")


def _validate_test_paths(test_paths: list[str]) -> None:
    if not test_paths:
        raise ValueError("test_paths must not be empty")
    for path in test_paths:
        if path.startswith("-"):
            raise ValueError(f"Invalid test path {path!r}: would be read as a command-line option")


def _tmpfs_volume(
    client: docker.DockerClient, purpose: str, size: str, owner: int = RUNNER_UID
) -> Any:
    # A root-owned volume must be readable by the sandbox user: 0755 instead of 0700.
    mode = "0700" if owner == RUNNER_UID else "0755"
    return client.volumes.create(
        name=f"assess-{purpose}-{uuid.uuid4().hex[:12]}",
        driver="local",
        driver_opts={
            "type": "tmpfs",
            "device": "tmpfs",
            "o": f"size={size},uid={owner},gid={owner},mode={mode}",
        },
        labels={"assess.runner": purpose},
    )


def _tar(files: dict[str, str], readonly: frozenset[str] = frozenset()) -> bytes:
    """Tar owned by the sandbox user, with explicit parent directories and runner dirs.

    Files in `readonly` are owned by root with mode 0444, and every directory above them
    is root-owned with mode 0755, so the sandbox user can't edit, delete, rename or replace
    them. Other directories stay writable.
    """
    dirs = {f"{RESERVED_DIR}", f"{RESERVED_DIR}/tmp", f"{RESERVED_DIR}/home"}
    for path in files:
        dirs.update(_ancestors(path))
    protected_dirs = {d for path in readonly for d in _ancestors(path)}

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for directory in sorted(dirs):
            uid = 0 if directory in protected_dirs else RUNNER_UID
            tar.addfile(_tar_info(directory, tarfile.DIRTYPE, 0o755, uid=uid))
        for path, content in files.items():
            data = content.encode()
            if path in readonly:
                info = _tar_info(path, tarfile.REGTYPE, 0o444, uid=0)
            else:
                info = _tar_info(path, tarfile.REGTYPE, 0o644)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _ancestors(path: str) -> list[str]:
    """Directories above `path`, excluding the workspace root: a/b/c.py -> [a, a/b]."""
    parts = path.split("/")[:-1]
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def _tar_info(name: str, kind: bytes, mode: int, uid: int = RUNNER_UID) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.mode = mode
    info.uid = info.gid = uid
    info.mtime = int(time.time())
    return info


def _wait_for_exit_code(
    container: Container, exit_code_path: str, deadline: float
) -> tuple[int | None, bool]:
    """Returns (exit code, timed out). The exit code is None if the launcher died."""
    while True:
        raw = _read_file(container, exit_code_path)
        if raw and raw.strip():
            try:
                return int(raw.strip()), False
            except ValueError:
                return None, False
        container.reload()
        if container.status != "running":
            return None, False
        if time.monotonic() >= deadline:
            return None, True
        time.sleep(POLL_INTERVAL_S)


def _read_file(container: Container, path: str) -> bytes | None:
    try:
        stream, _ = container.get_archive(path)
    except NotFound:
        return None
    with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as tar:
        member = tar.next()
        extracted = tar.extractfile(member) if member else None
        return extracted.read() if extracted else None


def _read_json(container: Container, path: str) -> dict[str, Any] | None:
    raw = _read_file(container, path)
    if raw is None:
        return None
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return report if isinstance(report, dict) else None


def _summarize(tests: list[TestResult]) -> Summary:
    passed = sum(test.outcome == "passed" for test in tests)
    failed = sum(test.outcome in ("failed", "error") for test in tests)
    return Summary(passed=passed, failed=failed, total=len(tests))


def _tail(output: bytes) -> str:
    return output[-TAIL_BYTES:].decode("utf-8", errors="replace")


def _cleanup(container: Container | None, volumes: list[Any]) -> None:
    if container is not None:
        try:
            container.remove(force=True)
        except APIError:
            logger.exception("Failed to remove sandbox container %s", container.id)
    for volume in volumes:
        try:
            volume.remove(force=True)
        except APIError:
            logger.exception("Failed to remove sandbox volume %s", volume.name)
