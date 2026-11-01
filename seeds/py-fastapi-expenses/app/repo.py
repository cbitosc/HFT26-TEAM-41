"""Database setup and queries."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Expense, User

# The fixed user table. A real app would store hashed tokens.
SEED_USERS = (("alice", "alice-token"), ("bob", "bob-token"))


def create_db() -> sessionmaker[Session]:
    """A fresh in-memory SQLite database with the schema and the seed users."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        # One shared connection, so every session sees the same in-memory database.
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    with session_factory.begin() as session:
        session.add_all(User(name=name, token=token) for name, token in SEED_USERS)
    return session_factory


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with request.app.state.session_factory() as session:
        yield session


def find_user_by_token(session: Session, token: str) -> User | None:
    """The user whose bearer token is `token`, or None."""
    return session.scalar(select(User).where(User.token == token))


def expenses_of(user_id: int) -> Select[tuple[Expense]]:
    """Base query for one user's expenses, to be filtered, sorted and paginated."""
    return select(Expense).where(Expense.user_id == user_id)


def insert_expense(session: Session, expense: Expense) -> Expense:
    session.add(expense)
    session.commit()
    return expense
