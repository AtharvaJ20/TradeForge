"""Add is_deleted to trades and import_source check constraint to execution_fills.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-07

Changes:
  1. trades.is_deleted — BOOLEAN NOT NULL DEFAULT false.
     Soft-delete flag for manually entered trades. The trade status is NOT
     changed by a soft-delete; is_deleted = true is the sole deletion signal.
     All queries surfacing trade rows to users must add is_deleted = false.
  2. idx_trades_user_active — partial index on trades (user_id) WHERE is_deleted = false.
     Standard composite index on (user_id, boolean) has poor selectivity because
     is_deleted = false represents ~100% of rows; the planner ignores it.
     A partial index is smaller and always used.
  3. ck_fills_import_source — new check constraint on execution_fills.import_source.
     The column was unconstrained in migration 0002. Adds the constraint now to
     enforce only 'CSV' and 'MANUAL' values.
  4. GRANT UPDATE (is_deleted) ON trades TO tradeforge_app — column-level grant.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add is_deleted column to trades
    # ------------------------------------------------------------------
    op.add_column(
        "trades",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ------------------------------------------------------------------
    # 2. Partial index: covers the common case (non-deleted rows) used by
    #    get_open_trade_with_lock() and other queries filtered by user_id.
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX idx_trades_user_active ON trades (user_id) WHERE is_deleted = false"
    )

    # ------------------------------------------------------------------
    # 3. Add import_source check constraint to execution_fills.
    #    The column was created unconstrained in migration 0002.
    #    Adding the constraint now with 'CSV' and 'MANUAL' values.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE execution_fills
        ADD CONSTRAINT ck_fills_import_source
        CHECK (import_source IN ('CSV', 'MANUAL'))
        """
    )

    # ------------------------------------------------------------------
    # 4. Column-level grant: tradeforge_app may UPDATE is_deleted.
    #    Full SELECT/INSERT/UPDATE/DELETE on trades was granted in 0002;
    #    this column-level grant is belt-and-suspenders for environments
    #    where column-level permissions are audited separately.
    # ------------------------------------------------------------------
    op.execute("GRANT UPDATE (is_deleted) ON trades TO tradeforge_app")


def downgrade() -> None:
    # Reverse the import_source constraint
    op.execute("ALTER TABLE execution_fills DROP CONSTRAINT IF EXISTS ck_fills_import_source")

    # Reverse the partial index
    op.execute("DROP INDEX IF EXISTS idx_trades_user_active")

    # Reverse the is_deleted column
    op.drop_column("trades", "is_deleted")
