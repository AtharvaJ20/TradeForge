"""Add starting_capital to trading_accounts (Step 18 — A-18-1).

Revision ID: f0a1b2c3d4e5
Revises: e1f2a3b4c5d6
Create Date: 2026-09-08

Changes:
  1. trading_accounts.starting_capital — NUMERIC(14,2) NULL DEFAULT NULL.
     Stores the user-declared opening capital for an account. Nullable because
     the field is optional at account creation; existing accounts are unaffected.
  2. No data backfill — existing rows get NULL.
  3. No NOT NULL constraint — the field remains permanently optional.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trading_accounts",
        sa.Column("starting_capital", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trading_accounts", "starting_capital")
