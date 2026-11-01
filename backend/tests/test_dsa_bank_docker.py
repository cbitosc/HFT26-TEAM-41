"""DSA bank tasks in real sandboxes (P2.6): Python and JS harness parity, the JS harness's
timeouts and load errors, and a full build with a fake LLM. Run with `make test-docker`."""

import pytest

from app import dsa, grading
from builder import dsa_bank
from builder.dsa_rewrite import DsaRewrite, RenamedParameter
from contracts_gen.task_spec import TaskSpec
from tests.test_dsa_bank import FakeLlm, names_for

pytestmark = pytest.mark.docker

# (problem, new function name, parameter renames, {runtime: (correct, wrong)})
PROBLEMS = [
    (
        "two_sum",
        "find_pair",
        {"nums": "amounts", "target": "goal"},
        {
            "python311": (
                "def find_pair(amounts, goal):\n"
                "    seen = {}\n"
                "    for i, x in enumerate(amounts):\n"
                "        if goal - x in seen:\n"
                "            return [i, seen[goal - x]]\n"
                "        seen[x] = i\n",
                "def find_pair(amounts, goal):\n    return [0, 1]\n",
            ),
            "node20": (
                "function find_pair(amounts, goal) {\n"
                "  const seen = new Map();\n"
                "  for (let i = 0; i < amounts.length; i++) {\n"
                "    if (seen.has(goal - amounts[i])) return [i, seen.get(goal - amounts[i])];\n"
                "    seen.set(amounts[i], i);\n"
                "  }\n"
                "}\n"
                "module.exports = { find_pair };\n",
                "module.exports = { find_pair: (amounts, goal) => [0, 1] };\n",
            ),
        },
    ),
    (
        "longest_unique_substring",
        "longest_clean_run",
        {"s": "log_line"},
        {
            "python311": (
                "def longest_clean_run(log_line):\n"
                "    last, start, best = {}, 0, 0\n"
                "    for i, c in enumerate(log_line):\n"
                "        if last.get(c, -1) >= start:\n"
                "            start = last[c] + 1\n"
                "        last[c] = i\n"
                "        best = max(best, i - start + 1)\n"
                "    return best\n",
                "def longest_clean_run(log_line):\n    return len(set(log_line))\n",
            ),
            "node20": (
                "function longest_clean_run(log_line) {\n"
                "  const last = new Map();\n"
                "  let start = 0, best = 0;\n"
                "  [...log_line].forEach((c, i) => {\n"
                "    if ((last.has(c) ? last.get(c) : -1) >= start) start = last.get(c) + 1;\n"
                "    last.set(c, i);\n"
                "    best = Math.max(best, i - start + 1);\n"
                "  });\n"
                "  return best;\n"
                "}\n"
                "module.exports = { longest_clean_run };\n",
                "module.exports = { longest_clean_run: (s) => new Set(s).size };\n",
            ),
        },
    ),
    (
        "best_time_to_buy_and_sell_stock",
        "best_margin",
        {"prices": "quotes"},
        {
            "python311": (
                "def best_margin(quotes):\n"
                "    low, best = float('inf'), 0\n"
                "    for q in quotes:\n"
                "        low = min(low, q)\n"
                "        best = max(best, q - low)\n"
                "    return best\n",
                "def best_margin(quotes):\n    return max(quotes) - min(quotes)\n",
            ),
            "node20": (
                "function best_margin(quotes) {\n"
                "  let low = Infinity, best = 0;\n"
                "  for (const q of quotes) {\n"
                "    low = Math.min(low, q);\n"
                "    best = Math.max(best, q - low);\n"
                "  }\n"
                "  return best;\n"
                "}\n"
                "module.exports = best_margin;\n",
                "module.exports = { best_margin: (q) => Math.max(...q) - Math.min(...q) };\n",
            ),
        },
    ),
]


def spec_for(problem_id, function, params, runtime) -> TaskSpec:
    problem = next(p for p in dsa_bank.load_bank() if p.id == problem_id)
    names = names_for(problem, function, params)
    return TaskSpec.model_validate(dsa_bank.task_spec(problem, "Story.", names, runtime, "novice"))


def outcomes(spec: TaskSpec, solution: str) -> dict[str, dict[str, str]]:
    grade = grading.grade_task(spec, {dsa_bank.SOLUTION_FILE[spec.runtime]: solution})
    assert grade.visible.status == grade.hidden.status == "ok", grade.visible.stderr_tail
    return {
        "visible": {t.id: t.outcome for t in grade.visible.tests},
        "hidden": {t.id: t.outcome for t in grade.hidden.tests},
    }


@pytest.mark.parametrize("problem_id, function, params, solutions", PROBLEMS)
def test_python_and_js_harnesses_agree(problem_id, function, params, solutions) -> None:
    py_spec = spec_for(problem_id, function, params, "python311")
    js_spec = spec_for(problem_id, function, params, "node20")
    for which in (0, 1):
        py = outcomes(py_spec, solutions["python311"][which])
        js = outcomes(js_spec, solutions["node20"][which])
        assert py == js, (problem_id, which)
        everything = list(py["visible"].values()) + list(py["hidden"].values())
        if which == 0:
            assert set(everything) == {"passed"}, problem_id
        else:
            assert "failed" in everything, problem_id


def test_js_starter_fails_and_case_ids_must_match() -> None:
    spec = spec_for(*PROBLEMS[0][:3], "node20")
    grade = grading.grade_task(spec, {})
    assert grade.visible.status == "ok" and not grade.visible_passed
    result = dsa.run_cases(spec, {}, spec.dsa_cases.visible, ["v1"])
    assert result.status == "error" and result.reason == dsa.TEST_SET_MISMATCH


def test_js_harness_times_out_per_case_and_carries_on() -> None:
    spec = spec_for(*PROBLEMS[1][:3], "node20")
    hang = (
        "function longest_clean_run(log_line) {\n"
        "  if (log_line === 'bbbbb') { while (true) {} }\n"
        "  return 3;\n"
        "}\n"
        "module.exports = { longest_clean_run };\n"
    )
    run = dsa.execute_cases(spec, {"solution.js": hang}, spec.dsa_cases.visible, 0.5)
    by_id = {e["id"]: e for e in run.report["cases"]}
    assert by_id["v2"]["error"] == "timed out after 0.5 s"
    assert by_id["v1"]["output"] == 3 and by_id["v3"]["output"] == 3


@pytest.mark.parametrize(
    "source, message",
    [
        ("module.exports = {};\n", "is not exported"),
        ("throw new Error('boom');\n", "Error: boom"),
        ("while (true) {}\n", "timed out"),
    ],
)
def test_js_harness_reports_a_function_that_cannot_load(source, message) -> None:
    spec = spec_for(*PROBLEMS[1][:3], "node20")
    result = dsa.run_cases(
        spec, {"solution.js": source}, spec.dsa_cases.visible, spec.visible_test_ids
    )
    assert result.status == "error" and message in result.stderr_tail


def test_js_non_json_output_is_an_error() -> None:
    spec = spec_for(*PROBLEMS[1][:3], "node20")
    source = "module.exports = { longest_clean_run: () => Infinity };\n"
    run = dsa.execute_cases(spec, {"solution.js": source}, spec.dsa_cases.visible[:1])
    assert "plain JSON" in run.report["cases"][0]["error"]


def test_build_checks_the_renamed_reference_in_the_sandbox(monkeypatch) -> None:
    problem = next(p for p in dsa_bank.load_bank() if p.id == "two_sum")
    good = DsaRewrite(
        statement="Our expenses API stores amounts; return the positions of two that hit the goal.",
        function_name="find_pair",
        parameters=[
            RenamedParameter(original="nums", renamed="amounts"),
            RenamedParameter(original="target", renamed="goal"),
        ],
    )
    from builder import dsa_rewrite

    monkeypatch.setattr(dsa_rewrite, "load_description", lambda p: "Original text.")
    built = dsa_bank.build_dsa_task(
        problem, "node20", "novice", "backend", ["expenses"], FakeLlm(good)
    )
    assert built.validation["statement"] == "llm"
    spec = TaskSpec.model_validate(built.spec)
    assert spec.certificate.reference_pass and spec.certificate.starter_fail
    assert set(spec.dsa_cases.visible[0].input) == {"amounts", "goal"}
