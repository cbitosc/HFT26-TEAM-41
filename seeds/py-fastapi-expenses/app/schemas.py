"""Request and response bodies."""

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.models import Category
from app.utils import parse_iso_date

MAX_AMOUNT_CENTS = 100_000_000  # 1,000,000.00

# Stricter than plain `date`, which would also accept timestamps like "1700000000".
IsoDate = Annotated[dt.date, BeforeValidator(parse_iso_date)]

# "-" prefix means descending.
SortKey = Literal["date", "-date", "amount", "-amount"]


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS, strict=True)
    category: Category
    date: IsoDate
    description: str = Field(default="", max_length=200)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_cents: int
    category: Category
    # Stored as Expense.spent_on, exposed as "date".
    date: dt.date = Field(validation_alias="spent_on")
    description: str


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    page: int
    page_size: int
    total: int
    has_next: bool


class MonthlyReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int
    month: int
    totals: dict[Category, int]
    """Cents spent per category; categories with no expenses are left out."""
    total_cents: int


class ImportResult(BaseModel):
    created: int
    skipped: int
    """Exact duplicates (date, amount, category, description) of stored or earlier items."""
