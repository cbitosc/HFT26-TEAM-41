"""Business logic: filtering, sorting, creating and importing expenses, monthly reports and
their cache."""

import datetime as dt
import threading
from collections import OrderedDict

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app import repo
from app.models import Category, Expense
from app.schemas import ExpenseCreate, ImportResult, MonthlyReport, SortKey
from app.utils import Page, month_bounds, paginate

_SORT_COLUMNS = {"date": Expense.spent_on, "amount": Expense.amount_cents}

ReportKey = tuple[int, int, int]  # (user_id, year, month)


class InvalidDateRange(ValueError):
    """date_from is after date_to."""


def apply_filters(
    stmt: Select,
    category: Category | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> Select:
    """Narrow `stmt` to one category and/or an inclusive date range."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise InvalidDateRange("date_from must not be after date_to")
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if date_from is not None:
        stmt = stmt.where(Expense.spent_on >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.spent_on <= date_to)
    return stmt


def apply_sorting(stmt: Select, sort: SortKey) -> Select:
    """Order by date or amount ("-" prefix: descending). Ties break on id, same direction."""
    column = _SORT_COLUMNS[sort.removeprefix("-")]
    if sort.startswith("-"):
        return stmt.order_by(column.desc(), Expense.id.desc())
    return stmt.order_by(column.asc(), Expense.id.asc())


def list_expenses(
    session: Session,
    user_id: int,
    *,
    category: Category | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    sort: SortKey,
    page: int,
    page_size: int,
) -> Page:
    stmt = apply_filters(repo.expenses_of(user_id), category, date_from, date_to)
    stmt = apply_sorting(stmt, sort)
    return paginate(session, stmt, page, page_size)


class ReportCache:
    """Monthly reports by (user_id, year, month). Bounded: the least recently used goes first."""

    def __init__(self, max_entries: int = 128) -> None:
        self._entries: OrderedDict[ReportKey, MonthlyReport] = OrderedDict()
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: ReportKey) -> MonthlyReport | None:
        with self._lock:
            report = self._entries.get(key)
            if report is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return report

    def put(self, key: ReportKey, report: MonthlyReport) -> None:
        with self._lock:
            self._entries[key] = report
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def invalidate(self, key: ReportKey) -> None:
        with self._lock:
            self._entries.pop(key, None)


def create_expense(
    session: Session, cache: ReportCache, user_id: int, data: ExpenseCreate
) -> Expense:
    """Store a new expense and drop the cached report for its month."""
    expense = Expense(
        user_id=user_id,
        amount_cents=data.amount_cents,
        category=data.category,
        spent_on=data.date,
        description=data.description,
    )
    repo.insert_expense(session, expense)
    cache.invalidate((user_id, data.date.year, data.date.month))
    return expense


def import_expenses(
    session: Session, cache: ReportCache, user_id: int, items: list[ExpenseCreate]
) -> ImportResult:
    """Store many expenses at once, skipping exact duplicates of stored or earlier items."""
    keys = list(
        dict.fromkeys((i.date, i.amount_cents, i.category.value, i.description) for i in items)
    )
    dates = sorted({key[0] for key in keys})
    stored = session.execute(
        select(Expense.spent_on, Expense.amount_cents, Expense.category, Expense.description).where(
            Expense.user_id == user_id, Expense.spent_on.in_(dates)
        )
    )
    existing = {tuple(row) for row in stored}
    new = [key for key in keys if key not in existing]
    session.add_all(
        Expense(user_id=user_id, spent_on=day, amount_cents=cents, category=cat, description=text)
        for day, cents, cat, text in new
    )
    session.commit()
    for year, month in {(day.year, day.month) for day, *_ in new}:
        cache.invalidate((user_id, year, month))
    return ImportResult(created=len(new), skipped=len(items) - len(new))


def compute_monthly_report(session: Session, user_id: int, year: int, month: int) -> MonthlyReport:
    """Cents spent per category in one calendar month."""
    start, end = month_bounds(year, month)
    rows = session.execute(
        select(Expense.category, func.sum(Expense.amount_cents))
        .where(Expense.user_id == user_id, Expense.spent_on >= start, Expense.spent_on < end)
        .group_by(Expense.category)
        .order_by(Expense.category)
    ).all()
    totals = {Category(category): int(total) for category, total in rows}
    return MonthlyReport(year=year, month=month, totals=totals, total_cents=sum(totals.values()))


def monthly_report(
    session: Session, cache: ReportCache, user_id: int, year: int, month: int
) -> MonthlyReport:
    """The monthly report, from the cache when possible."""
    key = (user_id, year, month)
    report = cache.get(key)
    if report is None:
        report = compute_monthly_report(session, user_id, year, month)
        cache.put(key, report)
    return report
