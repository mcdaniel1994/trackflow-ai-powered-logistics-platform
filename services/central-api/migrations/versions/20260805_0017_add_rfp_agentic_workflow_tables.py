"""Add the Engagement 9 RFP agentic workflow tables.

Creates ``rfp_tickets`` (lifecycle status + safe extracted metadata + converted Markdown),
``rfp_department_sections`` (per-department draft, evaluation, and human approval), and
``rfp_final_documents`` (the consolidated approved proposal). Node-level traceability reuses the
Engagement 8 agent trace store, so no audit table is added here.

Revision ID: 20260805_0017
Revises: 20260803_0016
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0017"
down_revision: str | None = "20260803_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TICKET_STATUS = (
    "'analyzing', 'waiting_for_approval', 'drafting', 'under_evaluation', 'done', 'discarded'"
)


def upgrade() -> None:
    op.create_table(
        "rfp_tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rfp_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("owner_user_uuid", sa.String(length=36), nullable=False),
        sa.Column("operator_jurisdiction", sa.String(length=2), nullable=True),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column("client_country", sa.String(length=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("services_requested", sa.JSON(), nullable=True),
        sa.Column("monthly_volume", sa.Integer(), nullable=True),
        sa.Column("deadline_days", sa.Integer(), nullable=True),
        sa.Column("budget_range", sa.String(length=120), nullable=True),
        sa.Column("departments_needed", sa.JSON(), nullable=True),
        sa.Column("readability_grade", sa.Float(), nullable=True),
        sa.Column("readability_metrics", sa.JSON(), nullable=True),
        sa.Column("markdown_text", sa.Text(), nullable=True),
        sa.Column("discard_reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"status IN ({TICKET_STATUS})", name="ck_rfp_tickets_status"),
        sa.CheckConstraint(
            "client_country IS NULL OR client_country IN ('US', 'ES')", name="ck_rfp_tickets_country"
        ),
        sa.CheckConstraint("currency IS NULL OR currency IN ('USD', 'EUR')", name="ck_rfp_tickets_currency"),
        sa.CheckConstraint(
            "operator_jurisdiction IS NULL OR operator_jurisdiction IN ('US', 'ES')",
            name="ck_rfp_tickets_operator_jurisdiction",
        ),
        sa.CheckConstraint("monthly_volume IS NULL OR monthly_volume >= 0", name="ck_rfp_tickets_volume"),
        sa.CheckConstraint("deadline_days IS NULL OR deadline_days >= 0", name="ck_rfp_tickets_deadline"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rfp_id"),
    )
    op.create_index("ix_rfp_tickets_owner_updated", "rfp_tickets", ["owner_user_uuid", "updated_at"])
    op.create_index("ix_rfp_tickets_status_updated", "rfp_tickets", ["status", "updated_at"])

    op.create_table(
        "rfp_department_sections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=16), nullable=False),
        sa.Column("key_aspects", sa.JSON(), nullable=True),
        sa.Column("draft_content", sa.Text(), nullable=True),
        sa.Column("evaluation_results", sa.JSON(), nullable=True),
        sa.Column("iteration_count", sa.Integer(), nullable=False),
        sa.Column("approval_status", sa.String(length=24), nullable=False),
        sa.Column("approver", sa.String(length=120), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected', 'changes_requested')",
            name="ck_rfp_sections_approval_status",
        ),
        sa.CheckConstraint(
            "department_id IN ('warehouse', 'lastmile', 'reverse')", name="ck_rfp_sections_department"
        ),
        sa.CheckConstraint("iteration_count >= 0", name="ck_rfp_sections_iterations"),
        sa.ForeignKeyConstraint(["ticket_id"], ["rfp_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "department_id", name="uq_rfp_sections_ticket_department"),
    )
    op.create_index("ix_rfp_sections_ticket", "rfp_department_sections", ["ticket_id"])

    op.create_table(
        "rfp_final_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency IN ('USD', 'EUR')", name="ck_rfp_final_currency"),
        sa.ForeignKeyConstraint(["ticket_id"], ["rfp_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", name="uq_rfp_final_ticket"),
    )


def downgrade() -> None:
    op.drop_table("rfp_final_documents")
    op.drop_index("ix_rfp_sections_ticket", table_name="rfp_department_sections")
    op.drop_table("rfp_department_sections")
    op.drop_index("ix_rfp_tickets_status_updated", table_name="rfp_tickets")
    op.drop_index("ix_rfp_tickets_owner_updated", table_name="rfp_tickets")
    op.drop_table("rfp_tickets")
