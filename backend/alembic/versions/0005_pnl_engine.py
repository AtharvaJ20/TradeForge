"""Step 10 — P&L engine: charge_schedules table with Zerodha seed data.

Creates:
  charge_schedules — broker/trade-type/exchange-segment charge rates with
                     effective-date versioning (Phase 1: no account_id, ADR-005).

Seed data:
  - Zerodha, post-Budget 2024 (effective 2024-10-01): 5 rows for NSE_EQ × {MIS, CNC,
    CNC_SAME_DAY} and NSE_FO × {NRML_FUT, NRML_OPT}.
  - Zerodha, pre-Budget 2024 (effective 2023-01-01): equity rows identical to 2024-10-01;
    F&O rows with pre-Budget STT rates.

Design: CHARGE-SCHEDULES-SPEC.md · ADR-005

Revision ID: e8c3a6f2d1b9
Revises: d7b3e1f5c2a4
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8c3a6f2d1b9"
down_revision: Union[str, None] = "d7b3e1f5c2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "charge_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("broker", sa.String(20), nullable=False),
        sa.Column("trade_type", sa.String(20), nullable=False),
        sa.Column("exchange_segment", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        # Brokerage
        sa.Column("brokerage_type", sa.String(20), nullable=False),
        sa.Column("brokerage_flat_per_order", sa.Numeric(18, 4), nullable=True),
        sa.Column("brokerage_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("brokerage_cap_per_order", sa.Numeric(18, 4), nullable=True),
        # STT
        sa.Column("stt_buy_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("stt_sell_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("stt_base", sa.String(10), nullable=False),
        # Exchange charges
        sa.Column("exchange_charge_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("exchange_charge_base", sa.String(10), nullable=False),
        # SEBI
        sa.Column("sebi_charge_rate", sa.Numeric(18, 8), nullable=False),
        # Stamp duty
        sa.Column("stamp_duty_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("stamp_duty_base", sa.String(10), nullable=False),
        # GST
        sa.Column("gst_rate", sa.Numeric(18, 8), nullable=False),
        # IPFT
        sa.Column("ipft_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("ipft_base", sa.String(10), nullable=False),
        # Audit
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker",
            "trade_type",
            "exchange_segment",
            "effective_from",
            name="uq_charge_schedules_lookup",
        ),
        sa.CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_charge_schedules_broker",
        ),
        sa.CheckConstraint(
            "trade_type IN ('MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT')",
            name="ck_charge_schedules_trade_type",
        ),
        sa.CheckConstraint(
            "exchange_segment IN ('NSE_EQ', 'NSE_FO', 'BSE_EQ')",
            name="ck_charge_schedules_exchange_segment",
        ),
        sa.CheckConstraint(
            "brokerage_type IN ('ZERO', 'FLAT', 'PERCENT_CAP')",
            name="ck_charge_schedules_brokerage_type",
        ),
        sa.CheckConstraint(
            "stt_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_stt_base",
        ),
        sa.CheckConstraint(
            "exchange_charge_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_exchange_base",
        ),
        sa.CheckConstraint(
            "stamp_duty_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_stamp_duty_base",
        ),
        sa.CheckConstraint(
            "ipft_base IN ('TURNOVER', 'PREMIUM')",
            name="ck_charge_schedules_ipft_base",
        ),
        sa.CheckConstraint(
            """(
                (brokerage_type = 'ZERO'
                     AND brokerage_flat_per_order IS NULL
                     AND brokerage_pct IS NULL
                     AND brokerage_cap_per_order IS NULL)
                OR
                (brokerage_type = 'FLAT'
                     AND brokerage_flat_per_order IS NOT NULL
                     AND brokerage_pct IS NULL
                     AND brokerage_cap_per_order IS NULL)
                OR
                (brokerage_type = 'PERCENT_CAP'
                     AND brokerage_flat_per_order IS NULL
                     AND brokerage_pct IS NOT NULL
                     AND brokerage_cap_per_order IS NOT NULL)
            )""",
            name="ck_charge_schedules_brokerage_cols",
        ),
        sa.CheckConstraint(
            "stt_buy_rate >= 0 AND stt_sell_rate >= 0 AND exchange_charge_rate >= 0"
            " AND sebi_charge_rate >= 0 AND stamp_duty_rate >= 0 AND gst_rate >= 0 AND ipft_rate >= 0",
            name="ck_charge_schedules_rates_non_negative",
        ),
    )
    op.create_index(
        "idx_charge_schedules_lookup",
        "charge_schedules",
        ["broker", "trade_type", "exchange_segment", sa.text("effective_from DESC")],
        postgresql_ops={"effective_from": "DESC"},
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON charge_schedules TO tradeforge_app")

    # ------------------------------------------------------------------
    # Seed data — Zerodha, post-Budget 2024 (effective 2024-10-01)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO charge_schedules (
            broker, trade_type, exchange_segment, effective_from,
            brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
            stt_buy_rate, stt_sell_rate, stt_base,
            exchange_charge_rate, exchange_charge_base,
            sebi_charge_rate,
            stamp_duty_rate, stamp_duty_base,
            gst_rate,
            ipft_rate, ipft_base,
            notes
        ) VALUES
        -- Row 1: MIS + NSE_EQ
        ('ZERODHA', 'MIS', 'NSE_EQ', '2024-10-01',
         'PERCENT_CAP', NULL, 0.00030000, 20.0000,
         0.00000000, 0.00025000, 'TURNOVER',
         0.00003450, 'TURNOVER',
         0.00000100,
         0.00003000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha equity intraday (MIS), NSE. Brokerage: lower of 0.03% or Rs20 per order side. STT sell-side 0.025%. Exchange 0.00345%. SEBI Rs10/crore. Stamp 0.003% buy. IPFT Rs10/crore.'),
        -- Row 2: CNC + NSE_EQ
        ('ZERODHA', 'CNC', 'NSE_EQ', '2024-10-01',
         'ZERO', NULL, NULL, NULL,
         0.00100000, 0.00100000, 'TURNOVER',
         0.00003450, 'TURNOVER',
         0.00000100,
         0.00015000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha equity delivery (CNC), NSE. Zero brokerage. STT 0.1% both sides. Stamp 0.015% buy.'),
        -- Row 3: CNC_SAME_DAY + NSE_EQ
        ('ZERODHA', 'CNC_SAME_DAY', 'NSE_EQ', '2024-10-01',
         'ZERO', NULL, NULL, NULL,
         0.00100000, 0.00100000, 'TURNOVER',
         0.00003450, 'TURNOVER',
         0.00000100,
         0.00015000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha CNC same-day, NSE. Delivery STT rates per TRADE-DOMAIN-RULES Rule 3.2. Zero brokerage.'),
        -- Row 4: NRML_FUT + NSE_FO (post-Budget 2024)
        ('ZERODHA', 'NRML_FUT', 'NSE_FO', '2024-10-01',
         'PERCENT_CAP', NULL, 0.00030000, 20.0000,
         0.00000000, 0.00020000, 'TURNOVER',
         0.00001880, 'TURNOVER',
         0.00000100,
         0.00002000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha NSE futures (NRML_FUT). STT sell 0.02% on turnover — raised from 0.0125% by Budget 2024, effective 2024-10-01.'),
        -- Row 5: NRML_OPT + NSE_FO (post-Budget 2024)
        ('ZERODHA', 'NRML_OPT', 'NSE_FO', '2024-10-01',
         'FLAT', 20.0000, NULL, NULL,
         0.00000000, 0.00100000, 'PREMIUM',
         0.00050300, 'PREMIUM',
         0.00000100,
         0.00003000, 'PREMIUM',
         0.18000000,
         0.00000100, 'PREMIUM',
         'Zerodha NSE options (NRML_OPT). Flat Rs20 per side. STT sell 0.1% on premium — raised from 0.0625% by Budget 2024, effective 2024-10-01.')
        """
    )

    # ------------------------------------------------------------------
    # Seed data — Zerodha, pre-Budget 2024 (effective 2023-01-01)
    # Equity rows identical to 2024-10-01; F&O rows use pre-Budget STT.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO charge_schedules (
            broker, trade_type, exchange_segment, effective_from,
            brokerage_type, brokerage_flat_per_order, brokerage_pct, brokerage_cap_per_order,
            stt_buy_rate, stt_sell_rate, stt_base,
            exchange_charge_rate, exchange_charge_base,
            sebi_charge_rate,
            stamp_duty_rate, stamp_duty_base,
            gst_rate,
            ipft_rate, ipft_base,
            notes
        ) VALUES
        -- Equity rows (MIS, CNC, CNC_SAME_DAY): identical to 2024-10-01
        ('ZERODHA', 'MIS', 'NSE_EQ', '2023-01-01',
         'PERCENT_CAP', NULL, 0.00030000, 20.0000,
         0.00000000, 0.00025000, 'TURNOVER',
         0.00003450, 'TURNOVER',
         0.00000100,
         0.00003000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha MIS NSE_EQ — historical (effective 2023-01-01), rates identical to 2024-10-01 for equity.'),
        ('ZERODHA', 'CNC', 'NSE_EQ', '2023-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00100000, 0.00100000, 'TURNOVER',
         0.00003450, 'TURNOVER',
         0.00000100,
         0.00015000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha CNC NSE_EQ — historical (effective 2023-01-01), rates identical to 2024-10-01 for equity.'),
        ('ZERODHA', 'CNC_SAME_DAY', 'NSE_EQ', '2023-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00100000, 0.00100000, 'TURNOVER',
         0.00003450, 'TURNOVER',
         0.00000100,
         0.00015000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha CNC_SAME_DAY NSE_EQ — historical (effective 2023-01-01), rates identical to 2024-10-01.'),
        -- Row 4H: NRML_FUT + NSE_FO (pre-Budget 2024: STT sell 0.0125%)
        ('ZERODHA', 'NRML_FUT', 'NSE_FO', '2023-01-01',
         'PERCENT_CAP', NULL, 0.00030000, 20.0000,
         0.00000000, 0.00012500, 'TURNOVER',
         0.00001880, 'TURNOVER',
         0.00000100,
         0.00002000, 'TURNOVER',
         0.18000000,
         0.00000100, 'TURNOVER',
         'Zerodha NSE futures (NRML_FUT). Pre-Budget-2024 rates. STT sell 0.0125% on turnover.'),
        -- Row 5H: NRML_OPT + NSE_FO (pre-Budget 2024: STT sell 0.0625%)
        ('ZERODHA', 'NRML_OPT', 'NSE_FO', '2023-01-01',
         'FLAT', 20.0000, NULL, NULL,
         0.00000000, 0.00062500, 'PREMIUM',
         0.00050300, 'PREMIUM',
         0.00000100,
         0.00003000, 'PREMIUM',
         0.18000000,
         0.00000100, 'PREMIUM',
         'Zerodha NSE options (NRML_OPT). Pre-Budget-2024 rates. STT sell 0.0625% on premium.')
        """
    )


def downgrade() -> None:
    op.drop_index("idx_charge_schedules_lookup", table_name="charge_schedules")
    op.drop_table("charge_schedules")
