"""Introduce trading_accounts table and nullable account_id FKs on trades, fills, pnl.

Adds the TradingAccount entity (ADR-005, ADR-006) and wires nullable account_id foreign
keys into the three core trade-domain tables.  The NOT NULL promotion is intentionally
deferred to migration 0009 (backfill) and a follow-on migration after WS-3.3 threads
account_id through the reconstruction engine.

Revision ID: b8c4d3e2f1a0
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01

CHECK constraints (ADR-006):
  account_type IN ('INDIVIDUAL', 'HUF')     — Phase 1 only; Phase 2 adds PROP/CORPORATE
  status       IN ('ACTIVE', 'INACTIVE')
  broker       IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')

Dedup partial unique index on execution_fills:
  uq_fills_broker_trade_account — (fill_id, account_id) WHERE fill_id IS NOT NULL
  Required by NORMALIZED-FILL-CONTRACT.md §4 for idempotent fill re-import.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "b8c4d3e2f1a0"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create trading_accounts table
    # ------------------------------------------------------------------
    op.create_table(
        "trading_accounts",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("broker", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(10), nullable=False, server_default="ACTIVE"),
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
        sa.CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_trading_accounts_broker",
        ),
        sa.CheckConstraint(
            "account_type IN ('INDIVIDUAL', 'HUF')",
            name="ck_trading_accounts_account_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_trading_accounts_status",
        ),
    )
    op.create_index("idx_trading_accounts_user_id", "trading_accounts", ["user_id"])

    # ------------------------------------------------------------------
    # 2. Nullable account_id FK on trades, execution_fills, trade_pnl
    # ------------------------------------------------------------------
    for table in ("trades", "execution_fills", "trade_pnl"):
        op.add_column(table, sa.Column("account_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_account_id",
            table,
            "trading_accounts",
            ["account_id"],
            ["id"],
        )
        op.create_index(f"idx_{table}_account_id", table, ["account_id"])

    # ------------------------------------------------------------------
    # 3. Dedup partial unique index for idempotent fill re-import
    # ------------------------------------------------------------------
    op.create_index(
        "uq_fills_broker_trade_account",
        "execution_fills",
        ["fill_id", "account_id"],
        unique=True,
        postgresql_where=sa.text("fill_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_fills_broker_trade_account", table_name="execution_fills")

    for table in reversed(("trades", "execution_fills", "trade_pnl")):
        op.drop_index(f"idx_{table}_account_id", table_name=table)
        op.drop_constraint(f"fk_{table}_account_id", table, type_="foreignkey")
        op.drop_column(table, "account_id")

    op.drop_index("idx_trading_accounts_user_id", table_name="trading_accounts")
    op.drop_table("trading_accounts")
