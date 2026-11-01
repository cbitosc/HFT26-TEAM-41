"""Validation gate (P2.7) in real sandboxes. Run with `make test-docker`."""

import pytest

from builder.manual import build_dsa_task
from gate import certify, check, rules_profile
from gate import core as gate_core
from tests.api_support import portfolio

pytestmark = pytest.mark.docker

# Appended to the reference's app/utils.py: every paginate() call fails half of the time.
FLAKY_PAGINATE = (
    "\n\n_paginate = paginate\n\n\n"
    "def paginate(*args, **kwargs):\n"
    "    import random\n\n"
    "    if random.random() < 0.5:\n"
    "        raise RuntimeError('coin flip')\n"
    "    return _paginate(*args, **kwargs)\n"
)


@pytest.fixture(scope="module")
def profile():
    return rules_profile(portfolio())


def test_the_seed_demo_domain_task_passes_the_gate(pagination_task, profile) -> None:
    spec, reasons = certify(pagination_task.spec, profile)

    assert reasons == []
    certificate = spec["certificate"]
    total = len(spec["visible_test_ids"]) + len(spec["hidden_test_ids"])
    assert certificate["reference_pass"] == f"{total}/{total} x3"
    assert certificate["starter_fail"] == f"1/{len(spec['visible_test_ids'])} visible"
    assert (certificate["scope_files"], certificate["changed_lines"]) == (["app/utils.py"], 1)
    assert certificate["mutation_score"] is None
    assert len(spec["fail_to_pass"]["hidden"]) == 2  # the other two failing pagination tests
    assert all("pagination" in i for i in spec["fail_to_pass"]["hidden"])


def test_the_seed_demo_dsa_task_passes_the_gate(profile) -> None:
    spec, reasons = certify(build_dsa_task().spec, profile)

    assert reasons == []
    assert spec["certificate"]["stub_fail_rate"] >= 0.9
    for split in ("visible", "hidden"):  # every case fails or passes on the starter, not both
        f2p, p2p = spec["fail_to_pass"][split], spec["pass_to_pass"][split]
        assert sorted(f2p + p2p) == sorted(spec[f"{split}_test_ids"]) and not set(f2p) & set(p2p)
    assert spec["fail_to_pass"]["visible"]


def test_a_really_flaky_reference_is_rejected(pagination_task, profile, monkeypatch) -> None:
    reference = gate_core.reference_files

    def flaky(spec):
        files = reference(spec)
        return files | {"app/utils.py": files["app/utils.py"] + FLAKY_PAGINATE}

    monkeypatch.setattr(gate_core, "reference_files", flaky)
    report = check(pagination_task.spec, profile, derive=lambda spec: spec)

    assert [r["code"] for r in report.reasons][:1] == ["reference_flaky"]


def test_mutation_testing_fills_the_mutation_score(pagination_task, profile) -> None:
    report = check(pagination_task.spec, profile, mutation=True)

    assert report.reasons == []
    assert 0.5 < report.certificate.mutation_score <= 1.0
