"""Generic helpers: pagination, date parsing, month ranges."""

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Page:
    items: list[Any]
    page: int
    page_size: int
    total: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total


def paginate(session: Session, stmt: Select, page: int, page_size: int) -> Page:
    """Run `stmt` for one 1-based page. `stmt` must already be filtered and sorted.

    A page past the end is empty but still reports the real total.
    """
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be at least 1")
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = session.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    items = list(session.scalars(stmt.limit(page_size).offset(offset)))
    return Page(items=items, page=page, page_size=page_size, total=total)


def parse_iso_date(value: object) -> dt.date:
    """Accept only a YYYY-MM-DD string naming a real calendar day."""
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise ValueError("must be a date in YYYY-MM-DD format")
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{value} is not a valid calendar date") from None


def month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    """First day of the month and first day of the next month (a half-open range)."""
    start = dt.date(year, month, 1)
    end = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    return start, end
