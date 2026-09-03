"""Migration 0011 — account_id NOT NULL promotion on trades, execution_fills, trade_pnl.

PREREQUISITE: This migration assumes every row in trades, execution_fills, and trade_pnl
already has a non-NULL account_id. Migration 0009 backfilled existing NULL rows for
development environments. In production, verify with:

    SELECT COUNT(*) FROM trades           WHERE account_id IS NULL;
    SELECT COUNT(*) FROM execution_fills  WHERE account_id IS NULL;
    SELECT COUNT(*) FROM trade_pnl        WHERE account_id IS NULL;

All three counts must be 0 before applying this migration. If any row has a NULL
account_id in production, the ALTER will fail with a constraint violation.

After Step 11 (ImportService), all newly created rows always have account_id set
via the import pipeline → ReconstructionEngine → PnlService chain.

Revision chain: 0010 (f2a8b7c6d5e4) → 0011 (a3b9c8d7e6f5)
"""

from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "a3b9c8d7e6f5"
down_revision: Union[str, None] = "f2a8b7c6d5e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("trades", "account_id", nullable=False)
    op.alter_column("execution_fills", "account_id", nullable=False)
    op.alter_column("trade_pnl", "account_id", nullable=False)


def downgrade() -> None:
    op.alter_column("trade_pnl", "account_id", nullable=True)
    op.alter_column("execution_fills", "account_id", nullable=True)
    op.alter_column("trades", "account_id", nullable=True)
