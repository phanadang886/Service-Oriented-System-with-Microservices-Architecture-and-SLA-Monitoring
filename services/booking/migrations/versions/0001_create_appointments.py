"""tao bang appointments

Revision ID: 0001
Revises:
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','CONFIRMED','CANCELLED')",
            name="ck_appointments_status",
        ),
    )
    op.create_index("ix_appointments_patient", "appointments", ["patient_id"])
    op.create_index("ix_appointments_slot", "appointments", ["slot_id"])


def downgrade() -> None:
    op.drop_index("ix_appointments_slot", table_name="appointments")
    op.drop_index("ix_appointments_patient", table_name="appointments")
    op.drop_table("appointments")