"""The migrations build the schema from an empty database and match app/models.py."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.models import Base
from tests.conftest import alembic_config, recreate_database

TABLES = {"assessments", "tasks", "sessions", "file_snapshots", "events", "runs", "scores"}


def test_upgrade_from_empty_matches_models_and_downgrades_cleanly() -> None:
    url = recreate_database("migrations_check")
    config = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(config, "head")
        with engine.connect() as conn:
            assert TABLES <= set(inspect(conn).get_table_names())
            assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []

        command.downgrade(config, "base")
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()
