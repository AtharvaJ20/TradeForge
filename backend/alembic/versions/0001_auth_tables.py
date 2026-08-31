"""Auth tables: users, pending_email_verifications, pending_password_resets, security_audit_log.

After running this migration for the first time, apply the INSERT-only grant on
security_audit_log (run as superuser against the dev DB — see docker/postgres/init.sql):

    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tradeforge_app;
    REVOKE DELETE, UPDATE, TRUNCATE ON security_audit_log FROM tradeforge_app;
    GRANT INSERT ON security_audit_log TO tradeforge_app;
    GRANT SELECT ON security_audit_log TO tradeforge_audit;

Revision ID: a8f3c1d9e5b2
Revises: (none — first migration)
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8f3c1d9e5b2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # pending_email_verifications
    # ------------------------------------------------------------------
    op.create_table(
        "pending_email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_email_verifications_email",
        "pending_email_verifications",
        ["email"],
    )
    op.create_index(
        "ix_pending_email_verifications_token_hash",
        "pending_email_verifications",
        ["token_hash"],
    )

    # ------------------------------------------------------------------
    # pending_password_resets
    # ------------------------------------------------------------------
    op.create_table(
        "pending_password_resets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_password_resets_email",
        "pending_password_resets",
        ["email"],
    )
    op.create_index(
        "ix_pending_password_resets_token_hash",
        "pending_password_resets",
        ["token_hash"],
    )

    # ------------------------------------------------------------------
    # security_audit_log (append-only; DELETE/UPDATE revoked from tradeforge_app)
    # ------------------------------------------------------------------
    op.create_table(
        "security_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_security_audit_log_user_id",
        "security_audit_log",
        ["user_id"],
    )
    op.create_index(
        "ix_security_audit_log_occurred_at",
        "security_audit_log",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("security_audit_log")
    op.drop_table("pending_password_resets")
    op.drop_table("pending_email_verifications")
    op.drop_table("users")
