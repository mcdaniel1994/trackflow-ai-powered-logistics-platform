"""Add the PostgreSQL-backed supplier directory.

Revision ID: 20260702_0003
Revises: 20260702_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_0003"
down_revision: str | None = "20260702_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country", sa.String(length=16), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("rate_per_shipment", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("service_zone", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("country IN ('USA', 'Spain')", name="ck_suppliers_country"),
        sa.CheckConstraint("currency IN ('USD', 'EUR')", name="ck_suppliers_currency"),
        sa.CheckConstraint(
            "(country = 'USA' AND currency = 'USD') OR (country = 'Spain' AND currency = 'EUR')",
            name="ck_suppliers_country_currency",
        ),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_suppliers_status"),
        sa.CheckConstraint("rate_per_shipment > 0", name="ck_suppliers_positive_rate"),
        sa.CheckConstraint(
            "jsonb_array_length(categories::jsonb) > 0 AND "
            "categories::jsonb <@ "
            "'[\"carrier_last_mile\", \"carrier_international\", \"warehouse_supplies\", "
            "\"packaging_materials\", \"reverse_logistics\", \"fleet_maintenance\", "
            "\"it_and_wms_software\", \"cleaning_and_facilities\"]'::jsonb",
            name="ck_suppliers_categories",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "country", name="uq_suppliers_name_country"),
    )
    op.create_index("ix_suppliers_country_name", "suppliers", ["country", "name"], unique=False)
    op.create_index("ix_suppliers_status", "suppliers", ["status"], unique=False)
    op.create_index(
        "uq_suppliers_name_country_ci",
        "suppliers",
        [sa.text("lower(name)"), "country"],
        unique=True,
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_suppliers_name_country_ci")
    op.drop_index("ix_suppliers_status", table_name="suppliers")
    op.drop_index("ix_suppliers_country_name", table_name="suppliers")
    op.drop_table("suppliers")
