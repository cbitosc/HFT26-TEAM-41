"""initial tables

events is append-only: a trigger rejects UPDATE, DELETE and TRUNCATE.

Revision ID: 0001
Revises:
Create Date: 2026-10-30 19:18:06.307212
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_FUNCTION = """
CREATE FUNCTION events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'events is append-only';
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_name", sa.Text(), nullable=False),
        sa.Column("portfolio", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("tier IN ('novice', 'adept', 'master')", name="ck_assessments_tier"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint("status IN ('active', 'submitted')", name="ck_sessions_status"),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "order"),
        sa.UniqueConstraint("assessment_id", "task_id"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_session_ts", "events", ["session_id", "ts"], unique=False)
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER events_no_update_delete BEFORE UPDATE OR DELETE ON events "
        "FOR EACH ROW EXECUTE FUNCTION events_append_only()"
    )
    op.execute(
        "CREATE TRIGGER events_no_truncate BEFORE TRUNCATE ON events "
        "FOR EACH STATEMENT EXECUTE FUNCTION events_append_only()"
    )
    op.create_table(
        "file_snapshots",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_file_snapshots_session_task_ts",
        "file_snapshots",
        ["session_id", "task_id", "ts"],
        unique=False,
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('visible', 'silent', 'submit')", name="ck_runs_kind"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_runs_session_task_ts", "runs", ["session_id", "task_id", "ts"], unique=False
    )
    op.create_table(
        "scores",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scores_session_id"), "scores", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scores_session_id"), table_name="scores")
    op.drop_table("scores")
    op.drop_index("ix_runs_session_task_ts", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_file_snapshots_session_task_ts", table_name="file_snapshots")
    op.drop_table("file_snapshots")
    op.drop_index("ix_events_session_ts", table_name="events")
    op.drop_table("events")
    op.execute("DROP FUNCTION events_append_only()")
    op.drop_table("tasks")
    op.drop_table("sessions")
    op.drop_table("assessments")
