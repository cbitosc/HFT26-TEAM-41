# Repo tour: Expenses API

A small FastAPI service for tracking expenses, backed by in-memory SQLite. Requests flow routes → services → repo.

- `app/main.py`: `create_app()` builds the app with a fresh database and report cache.
- `app/routes.py`: the three endpoints, `GET/POST /expenses` and `GET /reports/monthly`.
- `app/auth.py`: `get_current_user` checks the `Authorization: Bearer <token>` header.
- `app/services.py`: the business logic: `apply_filters`, `apply_sorting`, `create_expense`, monthly reports and `ReportCache`.
- `app/repo.py`: the database engine, the per-request session, and queries.
- `app/models.py`: SQLAlchemy tables (`User`, `Expense`) and the `Category` list.
- `app/schemas.py`: Pydantic request and response bodies, plus input rules.
- `app/utils.py`: generic helpers: `paginate`, `parse_iso_date`, `month_bounds`.
- `tests/`: one file per feature. `conftest.py` gives each test a fresh app and an `add_expense` helper.
- Test users: `alice-token` and `bob-token`. Amounts are integer cents.
- Run the tests with `pytest`.
