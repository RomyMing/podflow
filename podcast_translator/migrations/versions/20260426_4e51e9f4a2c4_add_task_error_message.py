"""add task error message

Revision ID: 4e51e9f4a2c4
Revises: b5ac5d548996
Create Date: 2026-04-26 22:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4e51e9f4a2c4"
down_revision: Union[str, None] = "b5ac5d548996"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("error_message", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "error_message")
