"""them unique partial index chong dat trung

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uniq_active_slot",
        "appointments",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status = 'CONFIRMED'"),
    )


def downgrade() -> None:
    op.drop_index("uniq_active_slot", table_name="appointments")