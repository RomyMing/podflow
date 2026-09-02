"""add elevenlabs voice observability

Revision ID: 6c7a4e2d9b8f
Revises: 1f9c8e7a6d2b
Create Date: 2026-05-26 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6c7a4e2d9b8f"
down_revision: Union[str, None] = "1f9c8e7a6d2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("speakers", sa.Column("voice_provider", sa.String(length=50), nullable=True))
    op.add_column("speakers", sa.Column("fallback_reason", sa.String(length=100), nullable=True))
    op.add_column("task_stage_runs", sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("task_stage_runs", "metrics")
    op.drop_column("speakers", "fallback_reason")
    op.drop_column("speakers", "voice_provider")
