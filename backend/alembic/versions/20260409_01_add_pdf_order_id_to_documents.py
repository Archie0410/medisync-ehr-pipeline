"""add pdf_order_id to documents

Revision ID: 20260409_01
Revises:
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260409_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("pdf_order_id", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_documents_pdf_order_id"), "documents", ["pdf_order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_pdf_order_id"), table_name="documents")
    op.drop_column("documents", "pdf_order_id")
