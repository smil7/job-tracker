"""initial schema: applications and status_events

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("wishlist", "applied", "assessment", "interview", "offer", "rejected", "withdrawn")
JOB_TYPES = ("graduate_program", "junior", "internship", "other")


def upgrade() -> None:
    status = postgresql.ENUM(*STATUSES, name="application_status", create_type=False)
    job_type = postgresql.ENUM(*JOB_TYPES, name="job_type", create_type=False)
    status.create(op.get_bind(), checkfirst=True)
    job_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("role", sa.String(200), nullable=False),
        sa.Column("job_url", sa.String(2000)),
        sa.Column("location", sa.String(200)),
        sa.Column("job_type", job_type),
        sa.Column("source", sa.String(100)),
        sa.Column("status", status, nullable=False),
        sa.Column("applied_at", sa.Date()),
        sa.Column("deadline", sa.Date()),
        sa.Column("salary", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("job_description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_applied_at", "applications", ["applied_at"])

    op.create_table(
        "status_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", status),
        sa.Column("to_status", status),
        sa.Column("note", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_status_events_application_id", "status_events", ["application_id"])


def downgrade() -> None:
    op.drop_table("status_events")
    op.drop_table("applications")
    sa.Enum(name="job_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="application_status").drop(op.get_bind(), checkfirst=True)
