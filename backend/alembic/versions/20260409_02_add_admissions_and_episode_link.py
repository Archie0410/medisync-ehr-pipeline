"""add admissions table and link episodes to admissions

Revision ID: 20260409_02
Revises: 20260409_01
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260409_02"
down_revision = "20260409_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("admission_date", sa.Date(), nullable=False),
        sa.Column("discharge_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("associated_episodes", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.UniqueConstraint("patient_id", "admission_date", "discharge_date", name="uq_admission_patient_dates"),
    )
    op.create_index(op.f("ix_admissions_patient_id"), "admissions", ["patient_id"], unique=False)
    op.create_index(op.f("ix_admissions_admission_date"), "admissions", ["admission_date"], unique=False)
    op.create_index(op.f("ix_admissions_discharge_date"), "admissions", ["discharge_date"], unique=False)

    op.add_column("episodes", sa.Column("admission_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_episodes_admission_id"), "episodes", ["admission_id"], unique=False)
    op.create_foreign_key(
        "fk_episodes_admission_id_admissions",
        "episodes",
        "admissions",
        ["admission_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_episodes_admission_id_admissions", "episodes", type_="foreignkey")
    op.drop_index(op.f("ix_episodes_admission_id"), table_name="episodes")
    op.drop_column("episodes", "admission_id")

    op.drop_index(op.f("ix_admissions_discharge_date"), table_name="admissions")
    op.drop_index(op.f("ix_admissions_admission_date"), table_name="admissions")
    op.drop_index(op.f("ix_admissions_patient_id"), table_name="admissions")
    op.drop_table("admissions")
