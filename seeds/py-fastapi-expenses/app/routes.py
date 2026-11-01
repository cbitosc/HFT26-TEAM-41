"""HTTP endpoints. Each handler reads the request, calls a service, and shapes the response."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import services
from app.auth import get_current_user
from app.models import Category, User
from app.repo import get_session
from app.schemas import (
    ExpenseCreate,
    ExpenseOut,
    ExpensePage,
    ImportResult,
    IsoDate,
    MonthlyReport,
    SortKey,
)

MAX_PAGE_SIZE = 100
MAX_IMPORT_ITEMS = 5_000

router = APIRouter()


def get_report_cache(request: Request) -> services.ReportCache:
    return request.app.state.report_cache


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_session)]
Cache = Annotated[services.ReportCache, Depends(get_report_cache)]


@router.get("/expenses")
def list_expenses(
    user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    category: Category | None = None,
    date_from: IsoDate | None = None,
    date_to: IsoDate | None = None,
    sort: SortKey = "-date",
) -> ExpensePage:
    try:
        result = services.list_expenses(
            session,
            user.id,
            category=category,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except services.InvalidDateRange as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return ExpensePage(
        items=[ExpenseOut.model_validate(expense) for expense in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        has_next=result.has_next,
    )


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(
    data: ExpenseCreate, user: CurrentUser, session: DbSession, cache: Cache
) -> ExpenseOut:
    expense = services.create_expense(session, cache, user.id, data)
    return ExpenseOut.model_validate(expense)


@router.post("/expenses/import")
def import_expenses(
    items: Annotated[list[ExpenseCreate], Body(min_length=1, max_length=MAX_IMPORT_ITEMS)],
    user: CurrentUser,
    session: DbSession,
    cache: Cache,
) -> ImportResult:
    """Create many expenses in one request; exact duplicates are skipped, not errors."""
    return services.import_expenses(session, cache, user.id, items)


@router.get("/reports/monthly")
def get_monthly_report(
    user: CurrentUser,
    session: DbSession,
    cache: Cache,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> MonthlyReport:
    """Cents spent per category by the current user in one calendar month."""
    return services.monthly_report(session, cache, user.id, year, month)
