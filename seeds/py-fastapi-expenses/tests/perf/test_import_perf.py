from app.schemas import ExpenseCreate
from app.services import import_expenses
from gen_large import ALICE, best_ms, expenses, import_batch, load
from sqlalchemy import delete, func, select

from app.main import create_app
from app.models import Expense


def test_import_into_a_large_history_is_fast(record_property):
    app = create_app()
    rows = expenses()
    load(app.state.session_factory, rows)
    batch, new = import_batch(rows)
    items = [ExpenseCreate.model_validate(item) for item in batch]
    results = []

    with app.state.session_factory() as session:
        last_id = session.scalar(select(func.max(Expense.id)))

        def run():
            results.append(import_expenses(session, app.state.report_cache, ALICE, items))

        def reset():
            session.execute(delete(Expense).where(Expense.id > last_id))
            session.commit()

        record_property("perf_ms", best_ms(run, reset))

    assert {(r.created, r.skipped) for r in results} == {(new, len(items) - new)}
