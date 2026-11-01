"""The validation gate (P2.7): run every soundness check on a task and write its certificate.

validate(spec, profile) -> (Certificate, []) when the task is sound, else (None, reasons).
Each reason is {"code", "detail", "items"}: a stable code the P2.9 repair loop acts on, a
sentence for people, and the ids or snippets involved. certify() also returns the spec with
the certificate and the fail_to_pass / pass_to_pass test ids filled in.

No LLM calls. Sandbox runs go through `grade` (app.grading.grade_task unless injected).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NoReturn

from app import grading
from builder.perf import PERF_DIR
from builder.tasks import load_seed
from contracts_gen.profile import Profile
from contracts_gen.task_spec import Certificate, TaskSpec, TestIdSplit
from gate import leak, limits
from gate.diff import diff
from gate.reference import reference_files, seed_renames
from gate.stubs import stub_fail_rates
from profiler.profile import build_profile

Reason = dict[str, Any]
Grade = Callable[[TaskSpec, dict[str, str]], grading.TaskGrade]
Derive = Callable[[dict[str, Any]], dict[str, Any]]
MutationScore = Callable[[TaskSpec, dict[str, str], list[str]], float | None]


def _no_llm(*_: Any, **__: Any) -> NoReturn:
    raise RuntimeError("the gate makes no LLM calls")


def rules_profile(portfolio: dict[str, Any]) -> Profile:
    """The portfolio's Profile from the profiler's rules only (its LLM fallback disabled)."""
    return build_profile(portfolio, llm=_no_llm)


def reason(code: str, detail: str, items: list[Any] | None = None) -> Reason:
    return {"code": code, "detail": detail, "items": list(items or [])}


@dataclass(frozen=True)
class GateReport:
    certificate: Certificate | None
    reasons: list[Reason]
    fail_to_pass: TestIdSplit | None = None
    pass_to_pass: TestIdSplit | None = None


def validate(
    spec: TaskSpec | dict[str, Any], profile: Profile | dict[str, Any], **options: Any
) -> tuple[Certificate | None, list[Reason]]:
    report = check(spec, profile, **options)
    return report.certificate, report.reasons


def certify(
    spec: TaskSpec | dict[str, Any], profile: Profile | dict[str, Any], **options: Any
) -> tuple[dict[str, Any] | None, list[Reason]]:
    """(the spec with certificate, fail_to_pass and pass_to_pass, []) or (None, reasons)."""
    task = _task(spec)
    report = check(task, profile, **options)
    if report.reasons:
        return None, report.reasons
    certified = task.model_copy(
        update={
            "certificate": report.certificate,
            "fail_to_pass": report.fail_to_pass,
            "pass_to_pass": report.pass_to_pass,
        }
    )
    return TaskSpec.model_validate(certified.model_dump()).model_dump(mode="json"), []


def check(
    spec: TaskSpec | dict[str, Any],
    profile: Profile | dict[str, Any],
    grade: Grade | None = None,
    derive: Derive | None = None,
    mutation: bool = False,
    mutation_score: MutationScore | None = None,
) -> GateReport:
    task = _task(spec)
    profile = profile if isinstance(profile, Profile) else Profile.model_validate(profile)
    grade = grade or grading.grade_task
    try:
        reference = reference_files(task)
    except ValueError as exc:
        return GateReport(None, [reason("reference_missing", str(exc))])

    id_reasons = _test_id_reasons(task, derive or grading.derive_test_ids)
    if id_reasons:  # runs can't be trusted with the wrong expected ids
        return GateReport(None, id_reasons)

    graded = _python_spec(task, reference) if task.kind == "dsa" else task
    runs = [grade(graded, reference) for _ in range(limits.REFERENCE_RUNS)]
    reasons = _reference_reasons(task, runs)
    starter = grade(task, {})
    fail_to_pass = TestIdSplit(
        visible=[i for i in task.visible_test_ids if i not in starter.visible_passed],
        hidden=[i for i in task.hidden_test_ids if i not in starter.hidden_passed],
    )
    pass_to_pass = TestIdSplit(
        visible=[i for i in task.visible_test_ids if i in starter.visible_passed],
        hidden=[i for i in task.hidden_test_ids if i in starter.hidden_passed],
    )
    reasons += _starter_reasons(task, fail_to_pass)
    reasons += _perf_reasons(task)

    stub_rate = changed_lines = None
    if task.kind == "domain":
        changes = diff(task.starter_files, reference)
        scope_files, changed_lines = changes.files, changes.changed_lines
        reasons += _novice_reasons(task, fail_to_pass)
        reasons += _scope_reasons(task, changes.files, changes.changed_lines)
        if leaks := leak.domain_leaks(task.statement_md, task.starter_files, reference):
            reasons.append(reason("statement_leak", "the statement gives the fix away", leaks))
    else:
        scope_files = sorted(task.starter_files)
        reasons += _tag_reasons(task, profile)
        rates = stub_fail_rates(task)
        stub_rate = min(rates.values()) if rates else 0.0
        if stub_rate < limits.STUB_MIN_FAIL_RATE:
            weak = [
                f"{name} fails {r:.0%}"
                for name, r in rates.items()
                if r < limits.STUB_MIN_FAIL_RATE
            ]
            reasons.append(
                reason(
                    "weak_tests",
                    f"a trivial stub fails only {stub_rate:.0%} of the cases "
                    f"(need {limits.STUB_MIN_FAIL_RATE:.0%})",
                    weak,
                )
            )
        if names := leak.name_leaks(task.statement_md, task.dsa_names):
            reasons.append(
                reason("statement_names_leak", "the statement uses the original names", names)
            )
    if reasons:
        return GateReport(None, reasons)

    score = None
    if mutation and task.kind == "domain":
        from gate import mutation as mutmut_run

        score = (mutation_score or mutmut_run.mutation_score)(task, reference, scope_files)
    draft = task.certificate
    total = len(task.visible_test_ids) + len(task.hidden_test_ids)
    certificate = Certificate(
        reference_pass=f"{total}/{total} x{limits.REFERENCE_RUNS}",
        starter_fail=f"{len(fail_to_pass.visible)}/{len(task.visible_test_ids)} visible",
        mutation_score=score,
        stub_fail_rate=round(stub_rate, 4) if stub_rate is not None else None,
        perf_ref_ms=draft.perf_ref_ms if task.perf else None,
        perf_naive_ms=draft.perf_naive_ms if task.perf else None,
        budget_ms=task.perf.budget_ms if task.perf else None,
        scope_files=scope_files,
        changed_lines=changed_lines,
    )
    return GateReport(certificate, [], fail_to_pass, pass_to_pass)


# --- Checks ---------------------------------------------------------------------------


def _task(spec: TaskSpec | dict[str, Any]) -> TaskSpec:
    return spec if isinstance(spec, TaskSpec) else TaskSpec.model_validate(spec)


def _python_spec(task: TaskSpec, reference: dict[str, str]) -> TaskSpec:
    """DSA references are Python: grade them on a Python copy of the task."""
    if task.runtime == "python311":
        return task
    return task.model_copy(update={"runtime": "python311", "starter_files": reference})


def _test_id_reasons(task: TaskSpec, derive: Derive) -> list[Reason]:
    try:
        derived = derive(task.model_dump(mode="json"))
    except (ValueError, RuntimeError) as exc:
        return [reason("test_ids_underivable", f"test ids could not be collected: {exc}")]
    reasons = []
    for split in ("visible", "hidden"):
        stored, found = set(getattr(task, f"{split}_test_ids")), set(derived[f"{split}_test_ids"])
        if stored != found:
            reasons.append(
                reason(
                    "test_ids_mismatch",
                    f"{split} test ids differ from the ones collected now",
                    sorted(stored ^ found),
                )
            )
    return reasons


def _outcomes(result: grading.TaskGrade) -> dict[str, str]:
    outcomes = {"<visible status>": result.visible.status, "<hidden status>": result.hidden.status}
    return outcomes | {t.id: t.outcome for t in result.visible.tests + result.hidden.tests}


def _reference_reasons(task: TaskSpec, runs: list[grading.TaskGrade]) -> list[Reason]:
    first = _outcomes(runs[0])
    differing = sorted(
        {key for run in runs[1:] for key, o in _outcomes(run).items() if first.get(key) != o}
        | {key for run in runs[1:] for key in first.keys() - _outcomes(run).keys()}
    )
    if differing:
        return [
            reason(
                "reference_flaky",
                f"the reference gave different results across {len(runs)} runs",
                differing,
            )
        ]
    run = runs[0]
    failing = sorted(
        (set(task.visible_test_ids) - run.visible_passed)
        | (set(task.hidden_test_ids) - run.hidden_passed)
    )
    if failing:
        return [reason("reference_fails", f"the reference fails {len(failing)} tests", failing)]
    return []


def _starter_reasons(task: TaskSpec, fail_to_pass: TestIdSplit) -> list[Reason]:
    if not fail_to_pass.visible:
        return [reason("starter_passes", "the starter passes every visible test")]
    if task.tier in limits.FAIL_BOTH_SPLITS and not fail_to_pass.hidden:
        return [reason("starter_passes_hidden", "the starter passes every hidden test")]
    return []


def _concept_ref(test_id: str) -> str:
    """tests/test_x_hidden.py::test_y[1] -> tests/test_x.py::test_y (as in concepts.yaml)."""
    path, _, name = test_id.partition("::")
    if path.endswith("_hidden.py"):
        path = path.removesuffix("_hidden.py") + ".py"
    return f"{path}::{name.split('[', 1)[0]}"


def _target_concept_tests(task: TaskSpec) -> set[str] | None:
    """The tests of the seed concept owning the target symbols, renamed like the task."""
    if not task.reference_ref.startswith("seeds/"):
        return None
    seed_id, renames = seed_renames(task.reference_ref)
    _, concepts = load_seed(seed_id)

    def renamed(text: str) -> str:
        if not renames:
            return text
        from builder.enrich import rename_text  # enrich imports gate.leak

        return rename_text(text, renames)

    for entry in concepts["concepts"].values():
        symbols = [renamed(s) for s in entry.get("symbols", [])]
        if any(t == s or t.startswith(s + ".") for s in symbols for t in task.target_symbols):
            return {renamed(t) for t in entry.get("tests", [])}
    return None


def _novice_reasons(task: TaskSpec, fail_to_pass: TestIdSplit) -> list[Reason]:
    if task.tier != "novice":
        return []
    concept_tests = _target_concept_tests(task)
    if concept_tests is None:
        return [
            reason(
                "unknown_target_concept",
                "no seed concept owns the target symbols",
                list(task.target_symbols),
            )
        ]
    outside = [
        i
        for i in fail_to_pass.visible + fail_to_pass.hidden
        if _concept_ref(i) not in concept_tests
    ]
    if outside:
        return [
            reason(
                "starter_breaks_other_concepts",
                f"the starter fails {len(outside)} tests outside the target concept",
                outside,
            )
        ]
    return []


def _scope_reasons(task: TaskSpec, files: list[str], changed_lines: int) -> list[Reason]:
    limit = limits.SCOPE[task.tier]
    reasons = []
    too_few = len(files) < limit.min_files
    too_many = limit.max_files is not None and len(files) > limit.max_files
    if too_few or too_many:
        wanted = (
            f"{limit.min_files}-{limit.max_files}"
            if limit.max_files is not None
            else f"at least {limit.min_files}"
        )
        if limit.min_files == limit.max_files:
            wanted = f"exactly {limit.min_files}"
        reasons.append(
            reason(
                "scope_files",
                f"the fix changes {len(files)} files; {task.tier} needs {wanted}",
                files,
            )
        )
    if limit.max_changed_lines is not None and changed_lines > limit.max_changed_lines:
        reasons.append(
            reason(
                "scope_lines",
                f"the fix changes {changed_lines} lines; {task.tier} allows at most "
                f"{limit.max_changed_lines}",
            )
        )
    return reasons


def _perf_reasons(task: TaskSpec) -> list[Reason]:
    """Perf calibration recorded by the builder (P2.4) in the draft certificate."""
    if task.perf is None:
        if limits.SCOPE[task.tier].needs_perf and task.kind == "domain":
            return [reason("perf_missing", f"{task.tier} tasks need a perf budget and calibration")]
        return []
    if task.kind == "domain" and not any(t.path.startswith(PERF_DIR) for t in task.hidden_tests):
        # grading.measure_perf times this test at submit; without it every submission
        # would get the perf floor.
        return [reason("perf_test_missing", f"perf is set but no hidden test is in {PERF_DIR}")]
    budget = task.perf.budget_ms
    ref_ms, naive_ms = task.certificate.perf_ref_ms, task.certificate.perf_naive_ms
    if ref_ms is None or naive_ms is None:
        return [reason("perf_uncalibrated", "perf_ref_ms and perf_naive_ms must both be measured")]
    reasons = []
    if ref_ms > budget:
        reasons.append(
            reason("perf_reference_over_budget", f"reference {ref_ms} ms > budget {budget} ms")
        )
    if naive_ms <= budget:
        reasons.append(
            reason("perf_starter_within_budget", f"starter {naive_ms} ms <= budget {budget} ms")
        )
    return reasons


def _tag_reasons(task: TaskSpec, profile: Profile) -> list[Reason]:
    allowed = {topic.root for topic in getattr(profile.allowed_topics, task.tier)}
    if bad := [tag for tag in task.dsa_tags if tag not in allowed]:
        return [
            reason(
                "tag_not_allowed",
                f"tags not in the profile's allowed {task.tier} topics "
                f"({', '.join(sorted(allowed)) or 'none'})",
                bad,
            )
        ]
    return []
