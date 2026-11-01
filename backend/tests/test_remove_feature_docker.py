"""Feature removal checked in real sandboxes. Run with `make test-docker`."""

import pytest

from builder.manual import EXPENSES_SEED
from builder.remove_feature import FeatureRemovalError, remove_feature
from builder.tasks import load_seed

pytestmark = pytest.mark.docker

_, CONCEPTS = load_seed(EXPENSES_SEED)
REPORTING_TESTS = CONCEPTS["concepts"]["reporting"]["tests"]


@pytest.fixture(scope="module")
def reporting():
    return remove_feature(EXPENSES_SEED, "reporting")


def test_starter_app_imports(reporting) -> None:
    assert reporting.checks.imports_ok
    assert "app.main" in reporting.checks.modules


def test_tests_of_other_concepts_pass_on_the_starter(reporting) -> None:
    checks = reporting.checks

    assert checks.other_tests > 30
    assert checks.other_failing == []
    assert checks.dependent_concepts == [
        "caching",
        "importing",
    ]  # calls the report code; tests hidden


def test_target_tests_fail_on_the_starter_and_pass_on_the_seed(reporting) -> None:
    checks = reporting.checks

    assert checks.target_failing_on_starter
    assert set(checks.target_failing_on_starter) <= set(REPORTING_TESTS)
    assert checks.target_failing_on_seed == []


def test_draft_is_a_validated_adept_spec(reporting) -> None:
    spec, validation = reporting.built.spec, reporting.built.validation

    assert (spec["tier"], spec["mode"], spec["kind"]) == ("adept", "seed", "domain")
    assert spec["certificate"]["scope_files"] == [
        "app/routes.py",
        "app/services.py",
        "app/utils.py",
    ]
    assert validation["starter_fails_visible"] and validation["reference_passes_all"]
    visible = {i.split("[")[0] for i in spec["visible_test_ids"]}
    assert all(i.startswith("tests/test_reports.py::") for i in visible)
    assert len(visible) == round(len(REPORTING_TESTS) / 3)


def test_concept_on_a_shared_path_is_rejected() -> None:
    with pytest.raises(FeatureRemovalError, match="breaks .* tests of other concepts"):
        remove_feature(EXPENSES_SEED, "auth")
