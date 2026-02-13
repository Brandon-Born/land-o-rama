"""Scrape artifacts provenance table

Revision ID: 0004_scrape_artifacts
Revises: 0003_opportunity_source_destination
Create Date: 2026-02-13 17:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_scrape_artifacts"
down_revision = "0003_opportunity_source_destination"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scrape_artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("county", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("local_path", sa.String(length=1024), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("records_found", sa.Integer(), nullable=False),
        sa.Column("records_accepted", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrape_artifacts_run_id", "scrape_artifacts", ["run_id"], unique=False)
    op.create_index("ix_scrape_artifacts_provider", "scrape_artifacts", ["provider"], unique=False)
    op.create_index("ix_scrape_artifacts_county", "scrape_artifacts", ["county"], unique=False)
    op.create_index("ix_scrape_artifacts_state", "scrape_artifacts", ["state"], unique=False)
    op.create_index("ix_scrape_artifacts_created_at", "scrape_artifacts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scrape_artifacts_created_at", table_name="scrape_artifacts")
    op.drop_index("ix_scrape_artifacts_state", table_name="scrape_artifacts")
    op.drop_index("ix_scrape_artifacts_county", table_name="scrape_artifacts")
    op.drop_index("ix_scrape_artifacts_provider", table_name="scrape_artifacts")
    op.drop_index("ix_scrape_artifacts_run_id", table_name="scrape_artifacts")
    op.drop_table("scrape_artifacts")
