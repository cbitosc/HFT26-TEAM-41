from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app import jobs
from app.cache import redis_client
from app.config import get_settings
from app.db import get_db
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def recreate_database(name: str) -> URL:
    """Drop and create database `name` on the compose Postgres; return its URL."""
    url = make_url(get_settings().database_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return url.set(database=name)


def alembic_config(url: URL) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    # configparser interpolation: escape % in the password.
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    return config


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """A fresh test database built by the migrations (never the dev database)."""
    url = recreate_database(f"{make_url(get_settings().database_url).database}_test")
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after the test, even when the code commits."""
    with db_engine.connect() as conn:
        outer = conn.begin()
        session = Session(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield session
        session.close()
        outer.rollback()


@pytest.fixture
def http(db: Session) -> Iterator[TestClient]:
    """API client whose requests use the test database session."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sent(monkeypatch) -> Iterator[list[dict]]:
    """Records Celery send_task calls instead of talking to the broker.

    Job records and run locks go to the real Redis (the lock needs SET NX) and are
    deleted afterwards.
    """
    calls: list[dict] = []
    monkeypatch.setattr(
        jobs.celery_app,
        "send_task",
        lambda name, args, task_id: calls.append({"name": name, "args": args, "task_id": task_id}),
    )
    yield calls
    for call in calls:
        redis_client.delete(f"job:{call['task_id']}", f"run_lock:{call['args'][0]}")


@pytest.fixture(scope="session")
def pagination_task():
    """The P1.3 demo domain task, built and validated in real sandboxes (Docker tests only)."""
    from builder.manual import build_pagination_task

    return build_pagination_task()
