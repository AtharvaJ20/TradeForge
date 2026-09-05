"""Add display_name, time_zone, base_currency to users table.

Revision ID: d0e1f2a3b4c5
Revises: c9d8e7f6a5b4
Create Date: 2026-09-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(100), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "time_zone",
            sa.String(60),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "base_currency",
            sa.String(3),
            nullable=False,
            server_default="INR",
        ),
    )
    op.execute("GRANT UPDATE (display_name, time_zone, base_currency) ON users TO tradeforge_app")


def downgrade() -> None:
    op.drop_column("users", "base_currency")
    op.drop_column("users", "time_zone")
    op.drop_column("users", "display_name")
