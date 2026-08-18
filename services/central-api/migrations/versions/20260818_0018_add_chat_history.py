"""Add owner-scoped chat sessions and messages.

Revision ID: 20260818_0018
Revises: 20260805_0017
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0018"
down_revision: str | None = "20260805_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("agent_id = 'first_line_cx'", name="ck_chat_sessions_agent"),
        sa.CheckConstraint(
            "status IN ('active', 'interrupted', 'closed')",
            name="ck_chat_sessions_status",
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_chat_sessions_user_updated",
        "chat_sessions",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "ix_chat_sessions_client_updated",
        "chat_sessions",
        ["client_id", "updated_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("interrupted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
        sa.CheckConstraint("sequence >= 1", name="ck_chat_messages_sequence"),
        sa.CheckConstraint("char_length(content) > 0", name="ck_chat_messages_content"),
        sa.CheckConstraint(
            "interrupted = false OR role = 'assistant'",
            name="ck_chat_messages_interrupted_role",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "uq_chat_messages_session_sequence",
        "chat_messages",
        ["session_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_chat_messages_session_sequence", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_client_updated", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_updated", table_name="chat_sessions")
    op.drop_table("chat_sessions")
