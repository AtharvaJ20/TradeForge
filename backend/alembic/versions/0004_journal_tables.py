"""Step 9 — Journal annotation layer.

Creates four tables:
  journal_entries    — 1:1 Layer B annotation per trade.
  journal_attachments — file attachments (PENDING → CONFIRMED lifecycle).
  journal_audit_log  — append-only field-level audit trail.
  trade_pnl          — empty stub; populated by Step 10 P&L engine.

Design decisions:
  - journal_entries.trade_id has a UNIQUE constraint (1:1 with trades).
  - journal_attachments.s3_key is server-generated ({user_id}/{trade_id}/{id});
    the client-supplied filename is metadata only (SR-ATT-005).
  - journal_audit_log is append-only (no trigger needed — service never updates rows).
  - trade_pnl is created here so journal GET responses have a stable API shape
    from day 1 (Option A, ADR-002). Journal service NEVER writes to trade_pnl.

Revision ID: d7b3e1f5c2a4
Revises: c4e2f9a1d8b5
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7b3e1f5c2a4"
down_revision: Union[str, None] = "c4e2f9a1d8b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMOTION_CHECK = (
    "'CALM', 'CONFIDENT', 'ANXIOUS', 'FEARFUL', 'GREEDY', "
    "'FRUSTRATED', 'EUPHORIC', 'BORED', 'DISTRACTED', 'NEUTRAL'"
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # journal_entries
    # ------------------------------------------------------------------
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Plan fields
        sa.Column("planned_entry", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_stop", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_target", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_risk_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("setup_name", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Behavioral fields
        sa.Column("discipline_score", sa.SmallInteger(), nullable=True),
        sa.Column(
            "mistakes",
            postgresql.ARRAY(sa.String(30)),
            nullable=True,
        ),
        sa.Column("emotion_before", sa.String(30), nullable=True),
        sa.Column("emotion_during", sa.String(30), nullable=True),
        sa.Column("emotion_after", sa.String(30), nullable=True),
        # Soft delete + timestamps
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("trade_id", name="uq_journal_entries_trade_id"),
        sa.CheckConstraint(
            "discipline_score IS NULL OR (discipline_score >= 1 AND discipline_score <= 10)",
            name="ck_journal_discipline_score",
        ),
        sa.CheckConstraint(
            f"emotion_before IS NULL OR emotion_before IN ({_EMOTION_CHECK})",
            name="ck_journal_emotion_before",
        ),
        sa.CheckConstraint(
            f"emotion_during IS NULL OR emotion_during IN ({_EMOTION_CHECK})",
            name="ck_journal_emotion_during",
        ),
        sa.CheckConstraint(
            f"emotion_after IS NULL OR emotion_after IN ({_EMOTION_CHECK})",
            name="ck_journal_emotion_after",
        ),
    )
    op.create_index("idx_journal_entries_user_id", "journal_entries", ["user_id"])
    op.create_index("idx_journal_entries_trade_id", "journal_entries", ["trade_id"])

    # ------------------------------------------------------------------
    # journal_attachments
    # ------------------------------------------------------------------
    op.create_table(
        "journal_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=False,
        ),
        # Server-generated S3 key: {user_id}/{trade_id}/{attachment_id} (SR-ATT-005)
        sa.Column("s3_key", sa.String(500), nullable=False),
        # filename: display metadata only — never used in S3 key (SR-ATT-005)
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("capture_moment", sa.String(20), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "capture_moment IN ('AT_ENTRY', 'DURING_TRADE', 'AT_EXIT', 'POST_REVIEW')",
            name="ck_attachment_capture_moment",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'EXPIRED', 'REJECTED')",
            name="ck_attachment_status",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_attachment_byte_size_positive"),
    )
    op.create_index("idx_attachments_journal_entry_id", "journal_attachments", ["journal_entry_id"])
    op.create_index("idx_attachments_user_id", "journal_attachments", ["user_id"])
    op.create_index("idx_attachments_trade_id", "journal_attachments", ["trade_id"])
    # Partial index for PENDING cleanup job (SR-ATT-010)
    op.create_index(
        "idx_attachments_pending",
        "journal_attachments",
        ["created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # ------------------------------------------------------------------
    # journal_audit_log  (append-only — no UPDATE or DELETE permitted)
    # ------------------------------------------------------------------
    op.create_table(
        "journal_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_journal_entry_id", "journal_audit_log", ["journal_entry_id"])
    op.create_index("idx_audit_log_user_id", "journal_audit_log", ["user_id"])

    # Append-only enforcement: block UPDATE and DELETE on journal_audit_log
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_journal_audit_log_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'journal_audit_log rows are append-only: DELETE is not permitted (id=%).',
                    OLD.id;
            END IF;
            RAISE EXCEPTION
                'journal_audit_log rows are append-only: UPDATE is not permitted (id=%).',
                OLD.id;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON journal_audit_log
        FOR EACH ROW EXECUTE FUNCTION trg_journal_audit_log_immutable()
        """
    )

    # ------------------------------------------------------------------
    # trade_pnl  (Step 10 P&L engine stub — charge breakdown added by 0007)
    # ------------------------------------------------------------------
    op.create_table(
        "trade_pnl",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        # Core P&L
        sa.Column("gross_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_charges", sa.Numeric(18, 4), nullable=False),
        sa.Column("r_multiple", sa.Numeric(18, 6), nullable=True),
        # Timestamps
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
        sa.UniqueConstraint("trade_id", name="uq_trade_pnl_trade_id"),
    )
    op.create_index("idx_trade_pnl_user_id", "trade_pnl", ["user_id"])

    # ------------------------------------------------------------------
    # Grants — extend tradeforge_app access to all four new tables
    # ------------------------------------------------------------------
    for table in ("journal_entries", "journal_attachments", "journal_audit_log", "trade_pnl"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO tradeforge_app")
    # journal_audit_log: tradeforge_app may only INSERT (trigger blocks UPDATE/DELETE)
    # The broad grant above is intentional — the trigger is the enforcement layer.


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON journal_audit_log")
    op.execute("DROP FUNCTION IF EXISTS trg_journal_audit_log_immutable()")

    op.drop_table("trade_pnl")
    op.drop_table("journal_audit_log")
    op.drop_table("journal_attachments")
    op.drop_table("journal_entries")
