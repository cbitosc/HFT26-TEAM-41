"""DSA test strength: how many cases trivial stubs get right.

The stubs are constant or identity functions, so their outputs are computed here on the
backend and compared with the expected values; nothing runs in a sandbox.
"""

from collections import Counter
from typing import Any

from app.dsa import matches
from builder.dsa_bank import load_bank
from contracts_gen.task_spec import TaskSpec

# Checked in order: bool before int (a JSON bool is a Python int).
_EMPTY_BY_JSON_TYPE = ((bool, False), (list, []), (dict, {}), (str, ""), (int, 0), (float, 0.0))
_EMPTY_BY_ANNOTATION = {"bool": False, "list": [], "dict": {}, "str": "", "int": 0, "float": 0.0}


def _first_argument(case_input: Any, first_param: str | None) -> Any:
    if isinstance(case_input, dict):
        if first_param is not None and first_param in case_input:
            return case_input[first_param]
        return next(iter(case_input.values()), None)
    if isinstance(case_input, list):
        return case_input[0] if case_input else None
    return case_input


def _empty_of_values(values: list[Any]) -> Any:
    """The empty value of the most common JSON type among the non-null expected values."""
    kinds = Counter(
        next((i for i, (kind, _) in enumerate(_EMPTY_BY_JSON_TYPE) if isinstance(v, kind)), None)
        for v in values
        if v is not None
    )
    kinds.pop(None, None)
    if not kinds:
        return None
    return _EMPTY_BY_JSON_TYPE[kinds.most_common(1)[0][0]][1]


def empty_value(spec: TaskSpec) -> Any:
    """The empty value of the task's return type: the bank signature's annotation when the
    problem is in the bank (`list[int]` -> []), else inferred from the expected values."""
    problem = next((p for p in load_bank() if p.id == spec.seed_id), None)
    if problem is not None:
        base = problem.signature.returns.split("[", 1)[0].strip()
        if base in _EMPTY_BY_ANNOTATION:
            return _EMPTY_BY_ANNOTATION[base]
    cases = spec.dsa_cases.visible + spec.dsa_cases.hidden
    return _empty_of_values([c.expected for c in cases])


def stub_fail_rates(spec: TaskSpec) -> dict[str, float]:
    """Share of all cases (visible + hidden) each stub fails, by stub name."""
    cases = spec.dsa_cases.visible + spec.dsa_cases.hidden
    if not cases:
        return {}
    empty = empty_value(spec)
    first_param = (
        spec.dsa_names.parameters[0].renamed
        if spec.dsa_names and spec.dsa_names.parameters
        else None
    )
    stubs = {
        "first_argument": lambda case_input: _first_argument(case_input, first_param),
        "empty_value": lambda _: empty,
        "zero": lambda _: 0,
        "none": lambda _: None,
    }
    comparator = spec.dsa_cases.comparator
    return {
        name: sum(not matches(stub(c.input), c.expected, comparator) for c in cases) / len(cases)
        for name, stub in stubs.items()
    }
