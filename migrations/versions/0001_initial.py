"""initial schema: locations, weather_readings_raw, weather_intelligence_daily, providers

Revision ID: 0001
Revises:
Create Date: 2026-07-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("normalized_key", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("normalized_key", name="uq_locations_normalized_key"),
    )

    op.create_table(
        "providers",
        sa.Column("name", sa.String(length=64), primary_key=True),
        sa.Column("data_class", sa.String(length=16), nullable=False),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "data_class IN ('forecast', 'historical')", name="ck_providers_data_class"
        ),
    )

    op.create_table(
        "weather_readings_raw",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_date", sa.Date(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_weather_readings_raw_location_valid_date",
        "weather_readings_raw",
        ["location_id", "valid_date"],
    )

    op.create_table(
        "weather_intelligence_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("risk_factors", postgresql.JSONB(), nullable=False),
        sa.Column("activity_scores", postgresql.JSONB(), nullable=False),
        sa.Column("packing", postgresql.JSONB(), nullable=False),
        sa.Column("travel_advisory", sa.String(length=16), nullable=False),
        sa.Column("rule_config_version", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "risk_level IN ('low', 'moderate', 'high')",
            name="ck_weather_intelligence_daily_risk_level",
        ),
        sa.CheckConstraint(
            "travel_advisory IN ('proceed', 'caution', 'avoid')",
            name="ck_weather_intelligence_daily_travel_advisory",
        ),
    )
    op.create_index(
        "ix_weather_intelligence_daily_location_date_version",
        "weather_intelligence_daily",
        ["location_id", "date", "rule_config_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weather_intelligence_daily_location_date_version",
        table_name="weather_intelligence_daily",
    )
    op.drop_table("weather_intelligence_daily")
    op.drop_index("ix_weather_readings_raw_location_valid_date", table_name="weather_readings_raw")
    op.drop_table("weather_readings_raw")
    op.drop_table("providers")
    op.drop_table("locations")
