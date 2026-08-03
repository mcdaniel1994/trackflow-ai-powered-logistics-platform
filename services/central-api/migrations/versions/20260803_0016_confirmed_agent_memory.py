"""Add human-confirmed structured agent memory.

Revision ID: 20260803_0016
Revises: 20260803_0015
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0016"
down_revision: str | None = "20260803_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'carrier_coverage_correction', 'carrier_assignment_correction', "
    "'recurring_operational_pattern', 'carrier_b2b_reporting_preference'"
)


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_uuid", sa.String(length=36), nullable=False),
        sa.Column("jurisdiction", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jurisdiction IN ('US', 'ES')", name="ck_agent_conversations_jurisdiction"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_conversations_owner_updated",
        "agent_conversations",
        ["owner_user_uuid", "updated_at"],
    )

    op.create_table(
        "agent_memory_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("carrier_id", sa.String(length=36), nullable=False),
        sa.Column("jurisdiction", sa.String(length=2), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("subject_key", sa.String(length=160), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("recurrence_count", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'discarded')",
            name="ck_agent_memory_proposals_status",
        ),
        sa.CheckConstraint("jurisdiction IN ('US', 'ES')", name="ck_agent_memory_proposals_jurisdiction"),
        sa.CheckConstraint(f"kind IN ({KINDS})", name="ck_agent_memory_proposals_kind"),
        sa.CheckConstraint("recurrence_count >= 2", name="ck_agent_memory_proposals_recurrence"),
        sa.ForeignKeyConstraint(["carrier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_agent_memory_proposals_one_pending",
        "agent_memory_proposals",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_agent_memory_proposals_pending_updated",
        "agent_memory_proposals",
        ["status", "updated_at"],
    )

    op.create_table(
        "agent_memory_facts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("carrier_id", sa.String(length=36), nullable=False),
        sa.Column("jurisdiction", sa.String(length=2), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("subject_key", sa.String(length=160), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("recurrence_count", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jurisdiction IN ('US', 'ES')", name="ck_agent_memory_facts_jurisdiction"),
        sa.CheckConstraint(f"kind IN ({KINDS})", name="ck_agent_memory_facts_kind"),
        sa.CheckConstraint("recurrence_count >= 2", name="ck_agent_memory_facts_recurrence"),
        sa.CheckConstraint("confirmation_count >= 1", name="ck_agent_memory_facts_confirmations"),
        sa.CheckConstraint("version >= 1", name="ck_agent_memory_facts_version"),
        sa.ForeignKeyConstraint(["carrier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "carrier_id",
            "jurisdiction",
            "kind",
            "subject_key",
            name="uq_agent_memory_facts_consolidation",
        ),
    )
    op.create_index(
        "ix_agent_memory_facts_carrier_jurisdiction_active",
        "agent_memory_facts",
        ["carrier_id", "jurisdiction", "active"],
    )

    op.create_table(
        "agent_memory_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("proposal_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_uuid", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=48), nullable=False),
        sa.Column("fact_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('approve', 'reject', 'edit')", name="ck_agent_memory_decisions_action"),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id"),
    )
    op.create_index(
        "ix_agent_memory_decisions_conversation_created",
        "agent_memory_decisions",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "agent_memory_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fact_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("carrier_id", sa.String(length=36), nullable=False),
        sa.Column("jurisdiction", sa.String(length=2), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("subject_key", sa.String(length=160), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("recurrence_count", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_user_uuid", sa.String(length=36), nullable=False),
        sa.Column("proposal_id", sa.String(length=36), nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_agent_memory_versions_version"),
        sa.ForeignKeyConstraint(["fact_id"], ["agent_memory_facts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fact_id", "version", name="uq_agent_memory_versions_fact_version"),
    )

    op.execute(
        """
        CREATE FUNCTION prevent_agent_memory_history_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'agent memory history is append-only';
        END;
        $$
        """
    )
    for table in ("agent_memory_decisions", "agent_memory_versions"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_agent_memory_history_mutation()"
        )


def downgrade() -> None:
    for table in ("agent_memory_versions", "agent_memory_decisions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_agent_memory_history_mutation()")
    op.drop_table("agent_memory_versions")
    op.drop_index("ix_agent_memory_decisions_conversation_created", table_name="agent_memory_decisions")
    op.drop_table("agent_memory_decisions")
    op.drop_index("ix_agent_memory_facts_carrier_jurisdiction_active", table_name="agent_memory_facts")
    op.drop_table("agent_memory_facts")
    op.drop_index("ix_agent_memory_proposals_pending_updated", table_name="agent_memory_proposals")
    op.drop_index("uq_agent_memory_proposals_one_pending", table_name="agent_memory_proposals")
    op.drop_table("agent_memory_proposals")
    op.drop_index("ix_agent_conversations_owner_updated", table_name="agent_conversations")
    op.drop_table("agent_conversations")
