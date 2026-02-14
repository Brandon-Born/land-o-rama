"""Add scrape artifact price summary columns

Revision ID: 0005_scrape_artifact_price_summary
Revises: 0004_scrape_artifacts
Create Date: 2026-02-14 03:25:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_scrape_artifact_price_summary"
down_revision = "0004_scrape_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scrape_artifacts", sa.Column("price_min", sa.Float(), nullable=True))
    op.add_column("scrape_artifacts", sa.Column("price_median", sa.Float(), nullable=True))
    op.add_column("scrape_artifacts", sa.Column("price_max", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("scrape_artifacts", "price_max")
    op.drop_column("scrape_artifacts", "price_median")
    op.drop_column("scrape_artifacts", "price_min")
