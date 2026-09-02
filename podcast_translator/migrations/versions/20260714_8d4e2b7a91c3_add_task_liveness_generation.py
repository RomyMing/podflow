"""add task liveness activity and generation

Revision ID: 8d4e2b7a91c3
Revises: 6c7a4e2d9b8f
Create Date: 2026-07-14 09:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d4e2b7a91c3"
down_revision: Union[str, None] = "6c7a4e2d9b8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("run_generation", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_tasks_status_last_activity_at",
        "tasks",
        ["status", "last_activity_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_status_last_activity_at", table_name="tasks")
    op.drop_column("tasks", "run_generation")
    op.drop_column("tasks", "last_activity_at")
