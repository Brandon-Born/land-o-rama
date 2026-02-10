"""Opportunity source destination fields

Revision ID: 0003_opportunity_source_destination
Revises: 0002_personalization
Create Date: 2026-02-10 16:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_opportunity_source_destination"
down_revision = "0002_personalization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("source_name", sa.String(length=128), nullable=True))
    op.add_column("opportunities", sa.Column("source_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunities", "source_url")
    op.drop_column("opportunities", "source_name")
