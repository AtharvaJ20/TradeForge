"""Backfill account_id for pre-existing local dev rows.

On a fresh production database (empty tables) all three UPDATE statements are
no-ops because no rows have account_id IS NULL.  The migration is safe to run
unconditionally.

On a local dev database with test data from Steps 1-10, this migration:
  1. Creates one 'Dev Default Account' per user that has unassigned rows.
  2. Links all existing rows (trades / execution_fills / trade_pnl) to that account.

NOT NULL promotion is intentionally excluded from this migration.  The ALTER COLUMN
SET NOT NULL step is deferred until WS-3.3 threads account_id through the
ReconstructionEngine (which creates trades via ORM without account_id today).
Promoting to NOT NULL before that step would break existing reconstruction
integration tests and any production code that creates trades directly.

Revision ID: c9d5e4f3a2b1
Revises: b8c4d3e2f1a0
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "c9d5e4f3a2b1"
down_revision: Union[str, None] = "b8c4d3e2f1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1 — create one dev account per user that has unassigned rows.
    # Uses gen_random_uuid() so each run produces a new UUID (idempotent:
    # if rows already have account_id, the INSERT is a no-op because the
    # subquery returns no rows for those users).
    conn.execute(
        text("""
        INSERT INTO trading_accounts
            (id, user_id, broker, display_name, account_type, base_currency, status)
        SELECT
            gen_random_uuid(),
            u.user_id,
            'MANUAL',
            'Dev Default Account',
            'INDIVIDUAL',
            'INR',
            'ACTIVE'
        FROM (
            SELECT DISTINCT user_id FROM trades           WHERE account_id IS NULL
            UNION
            SELECT DISTINCT user_id FROM execution_fills  WHERE account_id IS NULL
            UNION
            SELECT DISTINCT user_id FROM trade_pnl        WHERE account_id IS NULL
        ) u
        WHERE NOT EXISTS (
            SELECT 1 FROM trading_accounts ta WHERE ta.user_id = u.user_id
        )
    """)
    )

    # Step 2 — link existing rows to the dev account for their user.
    # At migration time each user has at most one account (just inserted above),
    # so the join is unambiguous.
    conn.execute(
        text("""
        UPDATE trades t
        SET account_id = ta.id
        FROM trading_accounts ta
        WHERE t.user_id = ta.user_id
          AND t.account_id IS NULL
    """)
    )
    conn.execute(
        text("""
        UPDATE execution_fills ef
        SET account_id = ta.id
        FROM trading_accounts ta
        WHERE ef.user_id = ta.user_id
          AND ef.account_id IS NULL
    """)
    )
    conn.execute(
        text("""
        UPDATE trade_pnl tp
        SET account_id = ta.id
        FROM trading_accounts ta
        WHERE tp.user_id = ta.user_id
          AND tp.account_id IS NULL
    """)
    )

    # NOT NULL promotion deferred — see module docstring.


def downgrade() -> None:
    # Backfill rows have no safe rollback without knowing which rows existed
    # before the migration.  Downgrade clears the account_id columns only;
    # the dev accounts themselves are NOT removed (they may be referenced by
    # integration test data from subsequent Steps).
    conn = op.get_bind()
    conn.execute(text("UPDATE trades           SET account_id = NULL"))
    conn.execute(text("UPDATE execution_fills  SET account_id = NULL"))
    conn.execute(text("UPDATE trade_pnl        SET account_id = NULL"))
