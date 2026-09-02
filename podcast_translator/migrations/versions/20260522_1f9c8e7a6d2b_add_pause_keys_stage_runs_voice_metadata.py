"""add pause api keys stage runs voice metadata

Revision ID: 1f9c8e7a6d2b
Revises: 9b2b6e7d41a1
Create Date: 2026-05-22 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1f9c8e7a6d2b"
down_revision: Union[str, None] = "9b2b6e7d41a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("pause_reason_code", sa.String(length=100), nullable=True))
    op.add_column("tasks", sa.Column("provider_error_code", sa.String(length=100), nullable=True))

    op.add_column("speakers", sa.Column("gender", sa.String(length=20), nullable=True))
    op.add_column("speakers", sa.Column("pitch_hz", sa.Float(), nullable=True))
    op.add_column("speakers", sa.Column("voice_id", sa.String(length=200), nullable=True))
    op.add_column("speakers", sa.Column("voice_model", sa.String(length=100), nullable=True))
    op.add_column("speakers", sa.Column("enrollment_status", sa.String(length=50), nullable=True))

    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("masked_key", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_api_keys_user_provider"),
    )

    op.create_table(
        "task_stage_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_total", sa.Integer(), nullable=True),
        sa.Column("items_done", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_stage_runs_task_stage", "task_stage_runs", ["task_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_task_stage_runs_task_stage", table_name="task_stage_runs")
    op.drop_table("task_stage_runs")
    op.drop_table("user_api_keys")

    op.drop_column("speakers", "enrollment_status")
    op.drop_column("speakers", "voice_model")
    op.drop_column("speakers", "voice_id")
    op.drop_column("speakers", "pitch_hz")
    op.drop_column("speakers", "gender")

    op.drop_column("tasks", "provider_error_code")
    op.drop_column("tasks", "pause_reason_code")
    op.drop_column("tasks", "paused_at")
