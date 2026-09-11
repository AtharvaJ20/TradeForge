"""Step 10 — P&L engine: MANUAL broker charge schedules (zero-rate).

Manual trades (broker='MANUAL') use zero-rate charge schedules so that
P&L is computed as gross P&L (price difference × quantity) with no
brokerage or tax deductions — the user entered the trade manually and
the system cannot infer actual charges.

Without these rows, ChargeScheduleNotFoundError was silently swallowed
inside the reconstruction engine and backfill_all_closed, leaving every
manually-entered trade with net_pnl=NULL (DEF-J4-001).

Seed data:
  - MANUAL, NSE_EQ × {MIS, CNC, CNC_SAME_DAY}
  - MANUAL, NSE_FO × {NRML_FUT, NRML_OPT}
  - MANUAL, BSE_EQ × {MIS, CNC, CNC_SAME_DAY}

All rows use brokerage_type='ZERO' and all rates = 0, effective from
2020-01-01 to cover all historical manual trades.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        -- NSE_EQ: MIS
        ('MANUAL', 'MIS', 'NSE_EQ', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- NSE_EQ: CNC
        ('MANUAL', 'CNC', 'NSE_EQ', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- NSE_EQ: CNC_SAME_DAY
        ('MANUAL', 'CNC_SAME_DAY', 'NSE_EQ', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- NSE_FO: NRML_FUT
        ('MANUAL', 'NRML_FUT', 'NSE_FO', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- NSE_FO: NRML_OPT
        ('MANUAL', 'NRML_OPT', 'NSE_FO', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'PREMIUM',
         0.00000000, 'PREMIUM',
         0.00000000,
         0.00000000, 'PREMIUM',
         0.00000000,
         0.00000000, 'PREMIUM',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- BSE_EQ: MIS
        ('MANUAL', 'MIS', 'BSE_EQ', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- BSE_EQ: CNC
        ('MANUAL', 'CNC', 'BSE_EQ', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.'),
        -- BSE_EQ: CNC_SAME_DAY
        ('MANUAL', 'CNC_SAME_DAY', 'BSE_EQ', '2020-01-01',
         'ZERO', NULL, NULL, NULL,
         0.00000000, 0.00000000, 'TURNOVER',
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         0.00000000,
         0.00000000, 'TURNOVER',
         'Manual trade — zero-rate schedule. P&L is gross (no charges deducted). DEF-J4-001.')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM charge_schedules WHERE broker = 'MANUAL'")
