"""Master builder and perf measurement in real sandboxes. Run with `make test-docker`."""

import pytest

from app import grading
from builder.manual import EXPENSES_SEED
from builder.master import budget_for, build_master
from builder.perf import PERF_DIR
from builder.tasks import load_seed
from contracts_gen.task_spec import TaskSpec

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def master():
    return build_master(EXPENSES_SEED, ["pagination"], 0)


def test_bug_and_perf_regression_are_in_different_files(master) -> None:
    spec = master.built.spec
    bug_symbol, perf_symbol = spec["target_symbols"]

    assert spec["tier"] == "master"
    assert bug_symbol.split("::")[0] != perf_symbol.split("::")[0]
    assert spec["certificate"]["scope_files"] == sorted(
        s.split("::")[0] for s in spec["target_symbols"]
    )


def test_budget_is_calibrated_and_the_regression_exceeds_it(master) -> None:
    spec, cal = master.built.spec, master.calibration

    assert len(cal.ref_runs) == 5
    assert spec["perf"]["budget_ms"] == cal.budget_ms == budget_for(cal.ref_runs)
    assert spec["certificate"]["perf_naive_ms"] > cal.budget_ms
    assert spec["certificate"]["perf_ref_ms"] == round(cal.ref_ms, 3)
    assert f"within {cal.budget_ms} ms" in spec["statement_md"]


def test_reference_passes_everything_including_perf(master) -> None:
    spec, validation = master.built.spec, master.built.validation
    perf_ids = [i for i in spec["hidden_test_ids"] if i.startswith(PERF_DIR)]

    assert len(perf_ids) == 1
    assert validation["reference_passes_all"]
    assert validation["starter_fails_visible"]


def test_perf_tests_are_hidden_only(master) -> None:
    spec = master.built.spec

    assert not any(p.startswith(PERF_DIR) for p in spec["starter_files"])
    assert not any(t["path"].startswith(PERF_DIR) for t in spec["visible_tests"])
    assert {t["path"] for t in spec["hidden_tests"] if t["path"].startswith(PERF_DIR)} == {
        "tests/perf/gen_large.py",
        "tests/perf/test_import_perf.py",
    }


def test_submit_measures_perf_ms_on_the_candidates_code(master) -> None:
    spec = TaskSpec.model_validate(master.built.spec)
    files, _ = load_seed(EXPENSES_SEED)
    perf_file = spec.target_symbols[-1].split("::")[0]

    fixed = grading.measure_perf(spec, {perf_file: files[perf_file]})
    untouched = grading.measure_perf(spec, {})

    assert fixed is not None and fixed <= spec.perf.budget_ms
    assert untouched is not None and untouched > spec.perf.budget_ms
