"""DSA harness, copied read-only into the sandbox. Not imported by the backend.

Usage: python -I python_cases.py <inputs.json> <report.json> <module.py> <function> <timeout s>

<inputs.json> is a list of {"id", "input"}: inputs only, never expected answers. Each input
is passed as keyword arguments (object), positional arguments (array) or a single argument.
The report is {"cases": [{"id", "output" | "error", "duration_ms"}]}, or {"fatal": "..."}
when the function can't be loaded. The backend compares outputs outside the sandbox.
"""

import importlib.util
import json
import signal
import sys
import time

ERROR_CHARS = 500


class CaseTimeout(BaseException):
    """BaseException, so a candidate's `except Exception` doesn't swallow it."""


def _on_alarm(signum, frame):
    raise CaseTimeout


def _write(path, report):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, allow_nan=False)


def _load(module_path, function_name):
    spec = importlib.util.spec_from_file_location("candidate_solution", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, function_name)


def _call(function, args):
    if isinstance(args, dict):
        return function(**args)
    if isinstance(args, list):
        return function(*args)
    return function(args)


def main():
    inputs_path, report_path, module_path, function_name, timeout = sys.argv[1:6]
    with open(inputs_path, encoding="utf-8") as f:
        cases = json.load(f)
    try:
        function = _load(module_path, function_name)
    except BaseException as exc:  # noqa: BLE001 - anything at import time is the candidate's
        message = f"could not load {function_name} from {module_path}: {type(exc).__name__}: {exc}"
        _write(report_path, {"fatal": message[:ERROR_CHARS]})
        return

    signal.signal(signal.SIGALRM, _on_alarm)
    results = []
    for case in cases:
        entry = {"id": case["id"]}
        started = time.monotonic()
        try:
            signal.setitimer(signal.ITIMER_REAL, float(timeout))
            try:
                output = _call(function, case["input"])
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            json.dumps(output, allow_nan=False)  # the output must be plain JSON
            entry["output"] = output
        except CaseTimeout:
            entry["error"] = f"timed out after {timeout} s"
        except Exception as exc:  # noqa: BLE001 - reported per case
            entry["error"] = f"{type(exc).__name__}: {exc}"[:ERROR_CHARS]
        entry["duration_ms"] = round((time.monotonic() - started) * 1000)
        results.append(entry)
    _write(report_path, {"cases": results})


if __name__ == "__main__":
    main()
