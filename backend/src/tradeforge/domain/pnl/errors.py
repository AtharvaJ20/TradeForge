"""P&L domain errors.

All are operational errors (expected failure paths), not programmer errors.
"""


class PnlCalculationError(Exception):
    """Base class for P&L calculation failures."""


class ChargeScheduleNotFoundError(PnlCalculationError):
    """No charge_schedules row found for (broker, trade_type, exchange_segment, trade_date).

    The trade remains in PENDING_CALCULATION state. This is a data-maintenance
    error — the seed data must cover every combination present in the trades table.
    """

    def __init__(
        self, broker: str, trade_type: str, exchange_segment: str, trade_date: object
    ) -> None:
        super().__init__(
            f"No charge schedule for broker={broker!r}, trade_type={trade_type!r}, "
            f"exchange_segment={exchange_segment!r}, trade_date={trade_date}"
        )
        self.broker = broker
        self.trade_type = trade_type
        self.exchange_segment = exchange_segment
        self.trade_date = trade_date


class LotSizeNotFoundError(PnlCalculationError):
    """No lot_size_history row found for the instrument on the trade date.

    Reserved for F&O lot-size lookups — not used in Step 10 (FIFO ruling confirms
    Step 10 reads average_entry/exit/total_entry_quantity as authoritative).
    """

    def __init__(self, instrument_id: object, trade_date: object) -> None:
        super().__init__(
            f"No lot size found for instrument_id={instrument_id} on trade_date={trade_date}"
        )
        self.instrument_id = instrument_id
        self.trade_date = trade_date
