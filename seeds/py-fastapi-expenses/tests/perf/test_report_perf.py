from collections import Counter

from app.services import ReportCache, monthly_report
from gen_large import ALICE, best_ms, expenses, load

from app.main import create_app

READS = 300  # a dashboard re-reading the same month


def test_repeated_monthly_reports_are_fast(record_property):
    app = create_app()
    rows = expenses()
    load(app.state.session_factory, rows)
    expected = Counter()
    for r in rows:
        if r["user_id"] == ALICE and (r["spent_on"].year, r["spent_on"].month) == (2025, 6):
            expected[r["category"]] += r["amount_cents"]
    totals = set()

    with app.state.session_factory() as session:

        def run():
            cache = ReportCache()
            for _ in range(READS):
                report = monthly_report(session, cache, ALICE, 2025, 6)
            totals.add(tuple(sorted(report.totals.items())))

        record_property("perf_ms", best_ms(run))

    assert totals == {tuple(sorted(expected.items()))}
