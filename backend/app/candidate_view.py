"""The only way a TaskSpec reaches the browser (CLAUDE.md rule 2)."""

from contracts_gen.candidate_task_view import (
    CandidateTaskView,
    DsaCase,
    PerfBudget,
    TestFile,
    VisibleDsaCases,
)
from contracts_gen.task_spec import TaskSpec


def to_candidate_view(spec: TaskSpec) -> CandidateTaskView:
    """Copy the browser-safe fields of `spec`, one by one.

    This is an allowlist on purpose: a field added to TaskSpec later stays on the backend
    until someone adds it here. reference_ref, target_symbols, hidden_tests, hidden DSA
    cases, the perf input generator, certificate and random_seeds are never copied.
    """
    return CandidateTaskView(
        task_id=spec.task_id,
        version=spec.version,
        tier=spec.tier,
        kind=spec.kind,
        runtime=spec.runtime,
        dsa_tags=list(spec.dsa_tags),
        statement_md=spec.statement_md,
        repo_tour_md=spec.repo_tour_md,
        starter_files=dict(spec.starter_files),
        entry_symbols=list(spec.entry_symbols),
        visible_tests=[TestFile(path=t.path, content=t.content) for t in spec.visible_tests],
        dsa_cases=(
            VisibleDsaCases(
                visible=[
                    DsaCase(id=c.id, input=c.input, expected=c.expected)
                    for c in spec.dsa_cases.visible
                ]
            )
            if spec.dsa_cases is not None
            else None
        ),
        perf=PerfBudget(budget_ms=spec.perf.budget_ms) if spec.perf is not None else None,
        time_budget_min=spec.time_budget_min,
    )
