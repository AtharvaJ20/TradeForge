"""Grant tradeforge_app access to trading_accounts table.

Migration 0008 created the trading_accounts table but omitted the GRANT
statement that every other migration applies. The tradeforge_app role has
SELECT/INSERT/UPDATE/DELETE on all other application tables; this migration
closes that gap.

Revision ID: c9d8e7f6a5b4
Revises: b1c2d3e4f5a6
Create Date: 2026-09-03
"""

from __future__ import annotations

from alembic import op

revision = "c9d8e7f6a5b4"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON trading_accounts TO tradeforge_app")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON trading_accounts FROM tradeforge_app")
