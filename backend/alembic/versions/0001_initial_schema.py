"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-02-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("listings_ingested", sa.Integer(), nullable=False),
        sa.Column("auctions_ingested", sa.Integer(), nullable=False),
        sa.Column("candidates_scored", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "listings_raw",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("county", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_listings_raw_external_id", "listings_raw", ["external_id"], unique=False)
    op.create_index("ix_listings_raw_county", "listings_raw", ["county"], unique=False)
    op.create_index("ix_listings_raw_state", "listings_raw", ["state"], unique=False)

    op.create_table(
        "auctions_raw",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("county", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auctions_raw_external_id", "auctions_raw", ["external_id"], unique=False)
    op.create_index("ix_auctions_raw_county", "auctions_raw", ["county"], unique=False)
    op.create_index("ix_auctions_raw_state", "auctions_raw", ["state"], unique=False)

    op.create_table(
        "parcels",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("parcel_key", sa.String(length=128), nullable=False),
        sa.Column("county", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("acreage", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("zoning", sa.String(length=64), nullable=False),
        sa.Column("legal_access", sa.Boolean(), nullable=False),
        sa.Column("utilities_hint", sa.String(length=128), nullable=False),
        sa.Column("flood_risk_level", sa.Integer(), nullable=False),
        sa.Column("wetland_risk_level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parcel_key"),
    )
    op.create_index("ix_parcels_parcel_key", "parcels", ["parcel_key"], unique=True)
    op.create_index("ix_parcels_county", "parcels", ["county"], unique=False)
    op.create_index("ix_parcels_state", "parcels", ["state"], unique=False)

    op.create_table(
        "market_metrics_daily",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("county", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("population_growth_1y", sa.Float(), nullable=False),
        sa.Column("jobs_growth_1y", sa.Float(), nullable=False),
        sa.Column("permit_growth_1y", sa.Float(), nullable=False),
        sa.Column("turnover_index", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_metrics_daily_county", "market_metrics_daily", ["county"], unique=False)
    op.create_index("ix_market_metrics_daily_state", "market_metrics_daily", ["state"], unique=False)
    op.create_index("ix_market_metrics_daily_as_of_date", "market_metrics_daily", ["as_of_date"], unique=False)

    op.create_table(
        "config_kv",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "provider_run_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_run_events_run_id", "provider_run_events", ["run_id"], unique=False)
    op.create_index("ix_provider_run_events_provider", "provider_run_events", ["provider"], unique=False)
    op.create_index("ix_provider_run_events_status", "provider_run_events", ["status"], unique=False)
    op.create_index("ix_provider_run_events_created_at", "provider_run_events", ["created_at"], unique=False)

    op.create_table(
        "feature_vectors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("parcel_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("market_growth_score", sa.Float(), nullable=False),
        sa.Column("development_pressure_score", sa.Float(), nullable=False),
        sa.Column("accessibility_score", sa.Float(), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("risk_penalty_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feature_vectors_parcel_id", "feature_vectors", ["parcel_id"], unique=False)
    op.create_index("ix_feature_vectors_run_id", "feature_vectors", ["run_id"], unique=False)
    op.create_index("ix_feature_vectors_as_of_date", "feature_vectors", ["as_of_date"], unique=False)

    op.create_table(
        "opportunities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("parcel_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("county", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("acreage", sa.Float(), nullable=False),
        sa.Column("base_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("is_excluded", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=256), nullable=True),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("caution_code", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunities_run_id", "opportunities", ["run_id"], unique=False)
    op.create_index("ix_opportunities_parcel_id", "opportunities", ["parcel_id"], unique=False)
    op.create_index("ix_opportunities_source_id", "opportunities", ["source_id"], unique=False)
    op.create_index("ix_opportunities_county", "opportunities", ["county"], unique=False)
    op.create_index("ix_opportunities_state", "opportunities", ["state"], unique=False)
    op.create_index("ix_opportunities_price", "opportunities", ["price"], unique=False)
    op.create_index("ix_opportunities_final_score", "opportunities", ["final_score"], unique=False)
    op.create_index("ix_opportunities_is_excluded", "opportunities", ["is_excluded"], unique=False)
    op.create_index("ix_opportunities_created_at", "opportunities", ["created_at"], unique=False)

    op.create_table(
        "risk_flags",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("parcel_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("flag", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("is_exclusionary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_flags_parcel_id", "risk_flags", ["parcel_id"], unique=False)
    op.create_index("ix_risk_flags_run_id", "risk_flags", ["run_id"], unique=False)

    op.create_table(
        "feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("opportunity_id", sa.String(), nullable=False),
        sa.Column("vote", sa.String(length=8), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_opportunity_id", "feedback", ["opportunity_id"], unique=False)
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"], unique=False)

    op.create_table(
        "digests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("opportunity_ids", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_digests_generated_at", "digests", ["generated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_digests_generated_at", table_name="digests")
    op.drop_table("digests")

    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_index("ix_feedback_opportunity_id", table_name="feedback")
    op.drop_table("feedback")

    op.drop_index("ix_risk_flags_run_id", table_name="risk_flags")
    op.drop_index("ix_risk_flags_parcel_id", table_name="risk_flags")
    op.drop_table("risk_flags")

    op.drop_index("ix_opportunities_created_at", table_name="opportunities")
    op.drop_index("ix_opportunities_is_excluded", table_name="opportunities")
    op.drop_index("ix_opportunities_final_score", table_name="opportunities")
    op.drop_index("ix_opportunities_price", table_name="opportunities")
    op.drop_index("ix_opportunities_state", table_name="opportunities")
    op.drop_index("ix_opportunities_county", table_name="opportunities")
    op.drop_index("ix_opportunities_source_id", table_name="opportunities")
    op.drop_index("ix_opportunities_parcel_id", table_name="opportunities")
    op.drop_index("ix_opportunities_run_id", table_name="opportunities")
    op.drop_table("opportunities")

    op.drop_index("ix_feature_vectors_as_of_date", table_name="feature_vectors")
    op.drop_index("ix_feature_vectors_run_id", table_name="feature_vectors")
    op.drop_index("ix_feature_vectors_parcel_id", table_name="feature_vectors")
    op.drop_table("feature_vectors")

    op.drop_index("ix_provider_run_events_created_at", table_name="provider_run_events")
    op.drop_index("ix_provider_run_events_status", table_name="provider_run_events")
    op.drop_index("ix_provider_run_events_provider", table_name="provider_run_events")
    op.drop_index("ix_provider_run_events_run_id", table_name="provider_run_events")
    op.drop_table("provider_run_events")

    op.drop_table("config_kv")

    op.drop_index("ix_market_metrics_daily_as_of_date", table_name="market_metrics_daily")
    op.drop_index("ix_market_metrics_daily_state", table_name="market_metrics_daily")
    op.drop_index("ix_market_metrics_daily_county", table_name="market_metrics_daily")
    op.drop_table("market_metrics_daily")

    op.drop_index("ix_parcels_state", table_name="parcels")
    op.drop_index("ix_parcels_county", table_name="parcels")
    op.drop_index("ix_parcels_parcel_key", table_name="parcels")
    op.drop_table("parcels")

    op.drop_index("ix_auctions_raw_state", table_name="auctions_raw")
    op.drop_index("ix_auctions_raw_county", table_name="auctions_raw")
    op.drop_index("ix_auctions_raw_external_id", table_name="auctions_raw")
    op.drop_table("auctions_raw")

    op.drop_index("ix_listings_raw_state", table_name="listings_raw")
    op.drop_index("ix_listings_raw_county", table_name="listings_raw")
    op.drop_index("ix_listings_raw_external_id", table_name="listings_raw")
    op.drop_table("listings_raw")

    op.drop_table("sync_runs")
