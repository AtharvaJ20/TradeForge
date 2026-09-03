"""Add analytics composite and partial indexes.

ADR-007 — Step 12 analytics layer.

New indexes:
  idx_trades_analytics          — covers every analytics base predicate
  idx_fills_exit_by_trade       — partial index for M-14 exit-type grouping (G-CORR-02)

Revision ID: b1c2d3e4f5a6
Revises: a3b9c8d7e6f5
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a3b9c8d7e6f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every analytics query's base predicate is:
    #   WHERE user_id = X AND status = 'CLOSED' AND trade_date BETWEEN Y AND Z
    # The existing idx_trades_user_status covers (user_id, status) but forces a
    # heap scan for the date range. This composite index turns the scan into an
    # index range scan for all 14 analytics base queries.
    op.create_index(
        "idx_trades_analytics",
        "trades",
        ["user_id", "status", "trade_date"],
        unique=False,
    )

    # M-14 uses DISTINCT ON (trade_id) ORDER BY trade_id, fill_timestamp DESC
    # scoped to fill_role = 'EXIT'. This partial index pre-filters to exit fills
    # stored in the required order — the DISTINCT ON becomes an index scan
    # with no additional sort step.
    op.create_index(
        "idx_fills_exit_by_trade",
        "execution_fills",
        ["trade_id", sa.text("fill_timestamp DESC")],
        unique=False,
        postgresql_where=sa.text("fill_role = 'EXIT'"),
    )


def downgrade() -> None:
    op.drop_index("idx_fills_exit_by_trade", table_name="execution_fills")
    op.drop_index("idx_trades_analytics", table_name="trades")
