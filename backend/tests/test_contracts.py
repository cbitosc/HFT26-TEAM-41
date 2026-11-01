"""Check every fixture in contracts/fixtures/ against its JSON Schema and its generated model."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from contracts_gen.candidate_task_view import CandidateTaskView
from contracts_gen.event import Event
from contracts_gen.portfolio import Portfolio
from contracts_gen.profile import Profile
from contracts_gen.run_result import RunResult
from contracts_gen.score_breakdown import ScoreBreakdown
from contracts_gen.task_spec import TaskSpec

# backend/tests/ -> repo root. In the api container this resolves to /contracts.
CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"

MODELS: dict[str, type[BaseModel]] = {
    "portfolio": Portfolio,
    "profile": Profile,
    "task_spec": TaskSpec,
    "candidate_task_view": CandidateTaskView,
    "event": Event,
    "run_result": RunResult,
    "score_breakdown": ScoreBreakdown,
}

# The reason each invalid fixture must be rejected, as a fragment of the jsonschema error.
# Pinning the reason stops a fixture from passing because of an unrelated mistake.
INVALID_REASONS = {
    "portfolio": "'assessment' is a required property",
    "profile": "'mobile' is not one of",
    "task_spec": "'expert' is not one of",
    "candidate_task_view": "'hidden_tests' was unexpected",
    "event": "is not valid under any of the given schemas",
    "run_result": "'crashed' is not one of",
    "score_breakdown": "'excellent' is not one of",
}

# TaskSpec fields that must never reach the browser (CLAUDE.md rule 2).
BACKEND_ONLY_FIELDS = {
    "reference_ref",
    "target_symbols",
    "hidden_tests",
    "certificate",
    "random_seeds",
}


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def validator_for(name: str) -> Draft202012Validator:
    schema = load(CONTRACTS_DIR / f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def fixture_params(kind: str) -> list:
    return [
        pytest.param(name, path, id=path.name)
        for name in MODELS
        for path in sorted(FIXTURES_DIR.glob(f"{name}.{kind}*.json"))
    ]


def test_every_schema_has_a_model_and_fixtures() -> None:
    schemas = {p.name.removesuffix(".schema.json") for p in CONTRACTS_DIR.glob("*.schema.json")}
    assert schemas == set(MODELS)
    for name in MODELS:
        assert list(FIXTURES_DIR.glob(f"{name}.valid*.json")), f"no valid fixture for {name}"
        assert (FIXTURES_DIR / f"{name}.invalid.json").is_file(), f"no invalid fixture for {name}"


@pytest.mark.parametrize(("name", "path"), fixture_params("valid"))
def test_valid_fixture(name: str, path: Path) -> None:
    doc = load(path)

    validator_for(name).validate(doc)
    model = MODELS[name].model_validate(doc)

    # The model must keep the document intact, extra JSON Resume fields included.
    assert model.model_dump(mode="json", by_alias=True, exclude_unset=True) == doc


@pytest.mark.parametrize(("name", "path"), fixture_params("invalid"))
def test_invalid_fixture(name: str, path: Path) -> None:
    doc = load(path)

    messages = [error.message for error in validator_for(name).iter_errors(doc)]
    assert any(INVALID_REASONS[name] in message for message in messages), messages
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(doc)


@pytest.mark.parametrize("name", ["task_spec", "candidate_task_view"])
def test_file_map_keys_use_the_rel_path_rule(name: str) -> None:
    # Inlined rather than $ref'd because the Python generator can't handle the $ref.
    defs = load(CONTRACTS_DIR / f"{name}.schema.json")["$defs"]

    assert defs["FileMap"]["propertyNames"]["pattern"] == defs["RelPath"]["pattern"]


def test_candidate_view_only_exposes_safe_task_spec_fields() -> None:
    spec = load(CONTRACTS_DIR / "task_spec.schema.json")
    view = load(CONTRACTS_DIR / "candidate_task_view.schema.json")
    view_fields = set(view["properties"])

    assert view["additionalProperties"] is False
    assert view_fields <= set(spec["properties"])
    assert not view_fields & BACKEND_ONLY_FIELDS
    assert set(view["$defs"]["VisibleDsaCases"]["properties"]) == {"visible"}
    assert set(view["$defs"]["PerfBudget"]["properties"]) == {"budget_ms"}
