"""add task source_file_name

Revision ID: 9b2b6e7d41a1
Revises: 20260427_d1f0b3d4bb25
Create Date: 2026-05-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b2b6e7d41a1"
down_revision = "d1f0b3d4bb25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("source_file_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "source_file_name")
