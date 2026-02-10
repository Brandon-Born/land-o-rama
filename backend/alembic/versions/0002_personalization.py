"""Personalization model schema

Revision ID: 0002_personalization
Revises: 0001_initial_schema
Create Date: 2026-02-10 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_personalization"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("personalization_score", sa.Float(), nullable=True))
    op.add_column("opportunities", sa.Column("model_version", sa.String(length=64), nullable=True))
    op.add_column(
        "opportunities",
        sa.Column("blend_weight", sa.Float(), nullable=False, server_default="0.15"),
    )

    op.create_table(
        "model_training_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("labels_used", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("artifact_path", sa.String(length=512), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_training_runs_model_version", "model_training_runs", ["model_version"], unique=False)
    op.create_index("ix_model_training_runs_trained_at", "model_training_runs", ["trained_at"], unique=False)
    op.create_index("ix_model_training_runs_status", "model_training_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_model_training_runs_status", table_name="model_training_runs")
    op.drop_index("ix_model_training_runs_trained_at", table_name="model_training_runs")
    op.drop_index("ix_model_training_runs_model_version", table_name="model_training_runs")
    op.drop_table("model_training_runs")

    op.drop_column("opportunities", "blend_weight")
    op.drop_column("opportunities", "model_version")
    op.drop_column("opportunities", "personalization_score")
