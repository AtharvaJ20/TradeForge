"""Expand trade_pnl with charge breakdown and engine metadata columns.

The table was originally created as a stub (gross_pnl, net_pnl, total_charges,
r_multiple only).  The ORM model and pnl_repo.upsert() expect the full schema
including per-component charge columns and engine metadata.  This migration
adds the missing columns and the two CHECK constraints.

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Charge component columns
    op.add_column(
        "trade_pnl", sa.Column("brokerage", sa.Numeric(18, 4), nullable=False, server_default="0")
    )
    op.add_column(
        "trade_pnl", sa.Column("stt", sa.Numeric(18, 4), nullable=False, server_default="0")
    )
    op.add_column(
        "trade_pnl",
        sa.Column("exchange_charges", sa.Numeric(18, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "trade_pnl",
        sa.Column("sebi_charges", sa.Numeric(18, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "trade_pnl", sa.Column("stamp_duty", sa.Numeric(18, 4), nullable=False, server_default="0")
    )
    op.add_column(
        "trade_pnl", sa.Column("gst", sa.Numeric(18, 4), nullable=False, server_default="0")
    )
    op.add_column(
        "trade_pnl", sa.Column("ipft", sa.Numeric(18, 4), nullable=False, server_default="0")
    )

    # Engine metadata columns
    op.add_column(
        "trade_pnl", sa.Column("broker", sa.String(20), nullable=False, server_default="UNKNOWN")
    )
    op.add_column(
        "trade_pnl",
        sa.Column(
            "charge_schedule_version", sa.String(50), nullable=False, server_default="legacy"
        ),
    )
    op.add_column(
        "trade_pnl",
        sa.Column("engine_version", sa.String(20), nullable=False, server_default="0.0.0"),
    )
    op.add_column(
        "trade_pnl",
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Drop server defaults after backfill so new rows must supply real values
    op.alter_column("trade_pnl", "brokerage", server_default=None)
    op.alter_column("trade_pnl", "stt", server_default=None)
    op.alter_column("trade_pnl", "exchange_charges", server_default=None)
    op.alter_column("trade_pnl", "sebi_charges", server_default=None)
    op.alter_column("trade_pnl", "stamp_duty", server_default=None)
    op.alter_column("trade_pnl", "gst", server_default=None)
    op.alter_column("trade_pnl", "ipft", server_default=None)
    op.alter_column("trade_pnl", "broker", server_default=None)
    op.alter_column("trade_pnl", "charge_schedule_version", server_default=None)
    op.alter_column("trade_pnl", "engine_version", server_default=None)

    # CHECK constraints
    op.create_check_constraint(
        "ck_trade_pnl_total_charges_identity",
        "trade_pnl",
        "total_charges = brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft",
    )
    op.create_check_constraint(
        "ck_trade_pnl_charges_non_negative",
        "trade_pnl",
        "brokerage >= 0 AND stt >= 0 AND exchange_charges >= 0 AND sebi_charges >= 0"
        " AND stamp_duty >= 0 AND gst >= 0 AND ipft >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_trade_pnl_charges_non_negative", "trade_pnl", type_="check")
    op.drop_constraint("ck_trade_pnl_total_charges_identity", "trade_pnl", type_="check")
    op.drop_column("trade_pnl", "calculated_at")
    op.drop_column("trade_pnl", "engine_version")
    op.drop_column("trade_pnl", "charge_schedule_version")
    op.drop_column("trade_pnl", "broker")
    op.drop_column("trade_pnl", "ipft")
    op.drop_column("trade_pnl", "gst")
    op.drop_column("trade_pnl", "stamp_duty")
    op.drop_column("trade_pnl", "sebi_charges")
    op.drop_column("trade_pnl", "exchange_charges")
    op.drop_column("trade_pnl", "stt")
    op.drop_column("trade_pnl", "brokerage")
