"""repair task error_message column

Revision ID: d1f0b3d4bb25
Revises: 4e51e9f4a2c4
Create Date: 2026-04-27 14:12:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d1f0b3d4bb25"
down_revision: Union[str, None] = "4e51e9f4a2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS error_message VARCHAR(1000)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS error_message")
