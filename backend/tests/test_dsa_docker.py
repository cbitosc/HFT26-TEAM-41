"""DSA grading in real sandboxes. Run with `make test-docker`."""

import pytest

from app import dsa, grading
from builder.manual import dsa_task_spec
from builder.seeds import DSA_DIR
from contracts_gen.task_spec import DsaCase, TaskSpec

pytestmark = pytest.mark.docker

# Built from two halves so this source file (and the scanner below) never contains them whole.
EXPECTED_MARKER = "EXPECTED" + "-c0ffee-answer"
INPUT_MARKER = "INPUT" + "-c0ffee-question"

# A candidate solution that searches the whole container for both markers.
SCANNER = """\
import os

SKIP = {"/proc", "/sys", "/dev", "/usr", "/lib", "/lib64", "/bin", "/sbin"}
MARKERS = {"expected": "EXPECTED" + "-c0ffee-answer", "input": "INPUT" + "-c0ffee-question"}


def _search(marker):
    needle = marker.encode()
    found = []
    for root, dirs, files in os.walk("/"):
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in SKIP]
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, "rb") as f:
                    if needle in f.read(10_000_000):
                        found.append(path)
            except OSError:
                pass
    for pid in filter(str.isdigit, os.listdir("/proc")):
        for part in ("cmdline", "environ"):
            try:
                with open(f"/proc/{pid}/{part}", "rb") as f:
                    if needle in f.read():
                        found.append(f"/proc/{pid}/{part}")
            except OSError:
                pass
    if needle in repr(os.environ).encode():
        found.append("os.environ")
    return sorted(found)


def length_of_longest_substring(s):
    return {kind: _search(marker) for kind, marker in MARKERS.items()}
"""


def test_candidate_finds_no_expected_values_anywhere_in_the_container() -> None:
    spec = TaskSpec.model_validate(dsa_task_spec())
    cases = [DsaCase(id="secret", input={"s": INPUT_MARKER}, expected=EXPECTED_MARKER)]

    run = dsa.execute_cases(spec, {"solution.py": SCANNER}, cases, case_timeout_s=60)

    assert run.status == "ok", run.stderr_tail
    [entry] = run.report["cases"]
    assert "error" not in entry, entry
    # Control: the scanner does find what is in the sandbox (the inputs file).
    assert "/workspace/_harness/inputs.json" in entry["output"]["input"]
    assert entry["output"]["expected"] == []


def test_reference_passes_and_stub_fails() -> None:
    spec = TaskSpec.model_validate(dsa_task_spec())
    reference = DSA_DIR / "longest_unique_substring" / "reference.py"
    files = {"solution.py": reference.read_text()}

    good = grading.grade_task(spec, files)
    stub = grading.run_visible(spec, {})

    assert good.visible_passed == set(spec.visible_test_ids)
    assert good.hidden_passed == set(spec.hidden_test_ids)
    assert stub.status == "ok"
    assert [t.outcome for t in stub.tests].count("passed") == 1  # only "" -> 0
    failing = next(t for t in stub.tests if t.outcome == "failed")
    assert failing.message == 'input {"s": "abcabcbb"}: expected 3, got 0'


def test_a_hanging_solution_times_out_per_case() -> None:
    spec = TaskSpec.model_validate(dsa_task_spec())
    hang = "def length_of_longest_substring(s):\n    while True:\n        pass\n"

    result = grading.run_visible(spec, {"solution.py": hang})

    assert result.status == "ok"
    assert {t.outcome for t in result.tests} == {"error"}
    assert all("timed out" in t.message for t in result.tests)


def test_a_broken_solution_is_an_error_with_the_reason() -> None:
    spec = TaskSpec.model_validate(dsa_task_spec())

    result = grading.run_visible(spec, {"solution.py": "def length_of_longest_substring(s:\n"})

    assert (result.status, result.tests) == ("error", [])
    assert "SyntaxError" in result.stderr_tail
