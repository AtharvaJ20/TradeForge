"""TradeService — orchestration for manual trade entry endpoints.

Owns the domain logic for:
  - create_trade()    — POST /v1/trades
  - add_fill()        — POST /v1/trades/{id}/fills
  - soft_delete_trade() — DELETE /v1/trades/{id}

The router (api/v1/trades.py) handles HTTP concerns; this service handles
domain orchestration. All methods operate within a caller-supplied AsyncSession
and do NOT commit — the router commits after a successful return.

Session contract (A-16-1 — Mayasura):
    TradeService.__init__ accepts one AsyncSession and distributes it to all
    repository constructors. All repos share the same session so that flushed
    writes are visible across repos within the same transaction (critical for
    the planned_risk_amount → get_planned_risk() ordering in BLK-1).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.application.pnl_service import PnlService
from tradeforge.application.trade.reconstruction import ReconstructionEngine
from tradeforge.application.trading_account_service import TradingAccountService
from tradeforge.domain.import_domain.errors import AccountInactiveError, AccountNotFoundError
from tradeforge.domain.import_domain.types import NormalizedFill
from tradeforge.domain.trade.errors import (
    ReconstructionConsistencyError,
    ReconstructionDataError,
)
from tradeforge.domain.trade.types import product_type_from_trade_type
from tradeforge.infrastructure.models.trade_domain import ExecutionFill, Trade
from tradeforge.infrastructure.repositories.charge_schedule_repo import ChargeScheduleRepository
from tradeforge.infrastructure.repositories.fill_exclusion_repo import FillExclusionRepository
from tradeforge.infrastructure.repositories.fill_repo import FillRepository
from tradeforge.infrastructure.repositories.instrument_repo import InstrumentRepository
from tradeforge.infrastructure.repositories.pnl_repo import PnlRepository
from tradeforge.infrastructure.repositories.tax_lot_repo import TaxLotRepository
from tradeforge.infrastructure.repositories.trade_repo import TradeRepository
from tradeforge.infrastructure.repositories.trading_account_repo import TradingAccountRepository

logger = logging.getLogger(__name__)

# Asia/Kolkata is UTC+05:30. Using a fixed offset avoids the tzdata dependency
# on Windows and matches the risk_service.py pattern.
_IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Domain errors — raised by TradeService, caught and mapped to HTTP by router
# ---------------------------------------------------------------------------


class TradeNotFoundError(Exception):
    def __init__(self, trade_id: uuid.UUID) -> None:
        self.trade_id = trade_id
        super().__init__(f"Trade {trade_id} not found or has been deleted")


class TradeNotOwnedError(Exception):
    def __init__(self, trade_id: uuid.UUID) -> None:
        self.trade_id = trade_id
        super().__init__(f"Trade {trade_id} is not owned by the authenticated user")


class TradeAlreadyClosedError(Exception):
    def __init__(self, trade_id: uuid.UUID) -> None:
        self.trade_id = trade_id
        super().__init__(f"Trade {trade_id} is already CLOSED")


class TradeNotManualError(Exception):
    def __init__(self, trade_id: uuid.UUID) -> None:
        self.trade_id = trade_id
        super().__init__(
            f"Trade {trade_id} contains broker-imported fills and cannot be deleted "
            "via this endpoint. Use the fill exclusion mechanism to dispute specific fills."
        )


class InstrumentNotFoundError(Exception):
    def __init__(self, symbol: str, exchange_segment: str, instrument_type: str) -> None:
        self.symbol = symbol
        self.exchange_segment = exchange_segment
        self.instrument_type = instrument_type
        super().__init__(
            f"Instrument not found: {symbol!r} / {exchange_segment!r} / {instrument_type!r}"
        )


class FillTimestampBeforeTradeOpenError(Exception):
    def __init__(self, fill_ts: datetime, first_fill_at: datetime) -> None:
        super().__init__(
            f"Fill timestamp {fill_ts.isoformat()} is before trade's first_fill_at "
            f"{first_fill_at.isoformat()}"
        )


class ReconstructionFailedError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Reconstruction failed: {detail}")


class PlannedStopWrongSideError(Exception):
    def __init__(self, direction: str, msg: str) -> None:
        self.direction = direction
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_fill_session(fill_timestamp: datetime) -> str:
    """Map a tz-aware fill_timestamp to the DB session enum value.

    Converts to Asia/Kolkata local time, then applies the rule:
      PRE_OPEN   — IST time before 09:15
      REGULAR    — IST time 09:15 to 15:30 (inclusive)
      POST_CLOSE — IST time after 15:30

    Note: the six N-2 analytics bands (Open Volatility, Mid-Morning, etc.) are
    computed at query time from fill_timestamp AT TIME ZONE 'Asia/Kolkata' by
    the analytics layer and are never stored in the session column.
    """
    ist_time = fill_timestamp.astimezone(_IST).time()
    if ist_time < time(9, 15):
        return "PRE_OPEN"
    if ist_time <= time(15, 30):
        return "REGULAR"
    return "POST_CLOSE"


def _derive_trade_date(fill_timestamp: datetime) -> "date":
    return fill_timestamp.astimezone(_IST).date()


# ---------------------------------------------------------------------------
# TradeService
# ---------------------------------------------------------------------------


class TradeService:
    """Orchestrates manual trade entry — create, add fill, soft-delete."""

    def __init__(self, session: AsyncSession) -> None:
        # All repos share the same session so flushed writes are visible across
        # repos within the same transaction (A-16-1 session contract).
        self._session = session
        self._account_svc = TradingAccountService(account_repo=TradingAccountRepository())
        self._instrument_repo = InstrumentRepository()
        self._fill_repo = FillRepository()
        self._fill_exclusion_repo = FillExclusionRepository()
        self._trade_repo = TradeRepository()
        self._pnl_service = PnlService(
            pnl_repo=PnlRepository(session),
            charge_schedule_repo=ChargeScheduleRepository(session),
        )
        self._engine = ReconstructionEngine(
            fill_repo=self._fill_repo,
            trade_repo=self._trade_repo,
            tax_lot_repo=TaxLotRepository(),
            fill_exclusion_repo=self._fill_exclusion_repo,
            pnl_service=self._pnl_service,
        )

    # -------------------------------------------------------------------------
    # create_trade — POST /v1/trades
    # -------------------------------------------------------------------------

    async def create_trade(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        instrument_symbol: str,
        exchange_segment: str,
        instrument_type: str,
        product_type: str,
        fills: list[dict],  # list of {side, quantity, price, fill_timestamp}
        expiry_date: date | None = None,
        strike_price: Decimal | None = None,
        planned_stop: Decimal | None = None,
        planned_target: Decimal | None = None,
    ) -> Trade:
        """Create a new trade from manual fills.

        Steps 1–11 per the execution plan. Returns the Trade ORM row for the
        affected trade (identified by ReconstructionResult.affected_trade_id).
        """
        session = self._session

        # Step 2: resolve account — must exist, be ACTIVE, and belong to user.
        # AccountNotFoundError / AccountInactiveError → router maps to 404.
        try:
            account = await self._account_svc.get_active(session, user_id, account_id)
        except AccountNotFoundError:
            raise
        except AccountInactiveError:
            # get_active raises AccountInactiveError for inactive accounts;
            # the router surface this as 404 ACCOUNT_NOT_FOUND per the plan.
            raise AccountNotFoundError(account_id)

        # Step 3: resolve instrument.
        instrument_id = await self._instrument_repo.find_for_fill(
            session,
            symbol=instrument_symbol,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_date=expiry_date,
            strike_price=strike_price,
        )
        if instrument_id is None:
            raise InstrumentNotFoundError(instrument_symbol, exchange_segment, instrument_type)

        # Step 4: insert each fill.
        for fill_dict in fills:
            fill_ts: datetime = fill_dict["fill_timestamp"]
            normalized = NormalizedFill(
                broker_trade_id=str(uuid.uuid4()),   # unique UUID per fill (D5)
                broker_order_id=str(uuid.uuid4()),
                broker="MANUAL",
                import_source="MANUAL",
                symbol_raw=instrument_symbol.upper(),
                exchange=exchange_segment.split("_")[0],  # e.g. "NSE"
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                expiry_date=expiry_date,
                strike_price=strike_price,
                trade_date=_derive_trade_date(fill_ts),
                fill_timestamp=fill_ts,
                session=_derive_fill_session(fill_ts),
                side=fill_dict["side"],
                quantity=fill_dict["quantity"],
                price=fill_dict["price"],
                product_type=product_type,
                is_auction=False,
                is_expiry_squareoff=False,
            )
            await self._fill_repo.insert_normalized_fill(
                session,
                user_id=user_id,
                account_id=account.id,
                instrument_id=instrument_id,
                fill=normalized,
            )

        # Step 5: flush so fills are visible to the reconstruction query.
        await session.flush()

        # Step 6: run reconstruction engine.
        try:
            result = await self._engine.run(
                session,
                user_id=user_id,
                account_id=account.id,
                instrument_id=instrument_id,
                product_type=product_type,
                instrument_type=instrument_type,
            )
        except (
            ReconstructionDataError,
            ReconstructionConsistencyError,
        ) as exc:
            raise ReconstructionFailedError(str(exc)) from exc

        # Step 7: get affected trade ID.
        if result.affected_trade_id is None:
            raise ReconstructionFailedError(
                "Reconstruction did not produce or resume a trade — no fills were processed"
            )
        affected_trade_id = result.affected_trade_id

        # Step 8: write planned_stop / planned_target / planned_risk_amount.
        # ORDERING CONSTRAINT (BLK-1): this must precede step 9 (backfill_all_closed).
        # PnlService.backfill_all_closed() reads trades.planned_risk_amount via the
        # get_planned_risk() fallback. If planned_risk_amount is not flushed before
        # backfill runs, the R-multiple is computed from NULL and persisted permanently.
        if planned_stop is not None or planned_target is not None:
            # Step 8a: query the trade row for direction + average_entry.
            trade_row = await session.get(Trade, affected_trade_id)
            if trade_row is None:
                raise ReconstructionFailedError(
                    f"Reconstruction claimed trade {affected_trade_id} was opened/continued "
                    "but the row was not found in the same transaction"
                )

            update_fields: dict = {}

            if planned_stop is not None:
                avg_entry = Decimal(str(trade_row.average_entry))
                direction = trade_row.direction

                # Step 8b: validate stop placement AFTER reconstruction (REQ-5).
                # Cannot validate at request time — direction is unknown until reconstruction.
                if direction == "LONG" and planned_stop >= avg_entry:
                    raise PlannedStopWrongSideError(
                        direction,
                        "Planned stop for a LONG trade must be below the average entry price.",
                    )
                if direction == "SHORT" and planned_stop <= avg_entry:
                    raise PlannedStopWrongSideError(
                        direction,
                        "Planned stop for a SHORT trade must be above the average entry price.",
                    )

                # Step 8c: compute planned_risk_amount.
                total_qty = Decimal(str(trade_row.total_entry_quantity))
                planned_risk_amount = abs(avg_entry - planned_stop) * total_qty
                update_fields["planned_stop"] = planned_stop
                update_fields["planned_risk_amount"] = planned_risk_amount

            if planned_target is not None:
                update_fields["planned_target"] = planned_target

            # Step 8d: write and flush before backfill.
            await self._trade_repo.update_trade(session, affected_trade_id, update_fields)
            await session.flush()

        # Step 9: backfill P&L for any trades closed by reconstruction.
        if result.trades_closed > 0:
            await self._pnl_service.backfill_all_closed(user_id)

        # Step 10: (caller commits)
        # Step 11: return the affected Trade row.
        # Re-fetch to get the fully updated state after all flushes.
        await session.refresh(await session.get(Trade, affected_trade_id))  # type: ignore[arg-type]
        trade_orm = await session.get(Trade, affected_trade_id)
        if trade_orm is None:
            raise ReconstructionFailedError(
                f"Trade {affected_trade_id} not found after reconstruction"
            )
        return trade_orm

    # -------------------------------------------------------------------------
    # add_fill — POST /v1/trades/{id}/fills
    # -------------------------------------------------------------------------

    async def add_fill(
        self,
        user_id: uuid.UUID,
        trade_id: uuid.UUID,
        fill_side: str,
        fill_quantity: Decimal,
        fill_price: Decimal,
        fill_timestamp: datetime,
    ) -> Trade:
        """Add a fill to an existing OPEN or PARTIAL trade.

        Mixed-provenance trades are permitted (D3 — Ganesha): a manual fill
        may be added to a CSV-imported trade to repair a gap in broker data.

        IMPORTANT — double-count risk (R-16-6 / D3 boundary condition):
        If the user adds a manual fill as gap-repair and a corrected CSV import
        later arrives containing the broker's version of that fill, both fills
        persist — fill_exists() checks broker_trade_id which is a UUID for
        manual fills and will not match the broker's fill ID. The position
        becomes double-counted. The manual fill MUST be excluded via
        fill_exclusions before re-importing the corrected CSV.
        Warning tooltip: "Added fills cannot be removed from this screen. If you
        add a fill in error and later receive a corrected broker import, contact
        support before importing." Phase 2 blocker: build fill-exclusion UI
        before enabling automated CSV re-import.
        """
        session = self._session

        # Step 1: look up the trade; must exist and not be soft-deleted.
        trade_row = await session.get(Trade, trade_id)
        if trade_row is None or trade_row.is_deleted:
            raise TradeNotFoundError(trade_id)

        # Step 2: ownership-only query — verify account belongs to user.
        # DO NOT use TradingAccountService.get() or get_active() here (REQ-6):
        # those methods check ACTIVE account status, which would incorrectly block
        # adds on trades from now-deactivated accounts. A user with an OPEN position
        # on a deactivated account should still be able to add corrective fills.
        # Only the trade's creation requires an ACTIVE account; subsequent fills do not.
        ownership_stmt = text(
            "SELECT id FROM trading_accounts WHERE id = :account_id AND user_id = :user_id"
        )
        ownership_result = await session.execute(
            ownership_stmt,
            {"account_id": str(trade_row.account_id), "user_id": str(user_id)},
        )
        if ownership_result.one_or_none() is None:
            raise TradeNotOwnedError(trade_id)

        # Step 3: closed trades cannot receive more fills via this endpoint.
        if trade_row.status == "CLOSED":
            raise TradeAlreadyClosedError(trade_id)

        # Step 4: validate fill_timestamp >= first_fill_at (AMB-01).
        first_fill_at = trade_row.first_fill_at
        if fill_timestamp.tzinfo is None:
            first_fill_at_naive = first_fill_at.replace(tzinfo=None)
            if fill_timestamp < first_fill_at_naive:
                raise FillTimestampBeforeTradeOpenError(fill_timestamp, first_fill_at)
        else:
            if fill_timestamp < first_fill_at:
                raise FillTimestampBeforeTradeOpenError(fill_timestamp, first_fill_at)

        # Step 5: derive instrument_type and product_type server-side.
        # instrument_type: query instruments table (not on Trade ORM).
        from tradeforge.infrastructure.models.trade_domain import Instrument  # noqa: PLC0415

        instrument_stmt = select(Instrument.instrument_type).where(
            Instrument.id == trade_row.instrument_id
        )
        instr_result = await session.execute(instrument_stmt)
        instrument_type = instr_result.scalar_one_or_none()
        if instrument_type is None:
            raise ReconstructionFailedError(
                f"Instrument {trade_row.instrument_id} not found for trade {trade_id}"
            )

        # product_type: derived from trade.trade_type (D6 — Ganesha).
        product_type = product_type_from_trade_type(trade_row.trade_type)

        # Step 6: insert the fill.
        # symbol_raw, exchange, exchange_segment are not stored on ExecutionFill
        # (insert_normalized_fill maps only the fill fields; instrument_id is
        # already resolved). We pass placeholder values for these required fields.
        normalized = NormalizedFill(
            broker_trade_id=str(uuid.uuid4()),
            broker_order_id=str(uuid.uuid4()),
            broker="MANUAL",
            import_source="MANUAL",
            symbol_raw="MANUAL",
            exchange="MANUAL",
            exchange_segment="MANUAL",
            instrument_type=instrument_type,
            expiry_date=None,
            strike_price=None,
            trade_date=_derive_trade_date(fill_timestamp),
            fill_timestamp=fill_timestamp,
            session=_derive_fill_session(fill_timestamp),
            side=fill_side,
            quantity=fill_quantity,
            price=fill_price,
            product_type=product_type,
            is_auction=False,
            is_expiry_squareoff=False,
        )
        await self._fill_repo.insert_normalized_fill(
            session,
            user_id=user_id,
            account_id=trade_row.account_id,
            instrument_id=trade_row.instrument_id,
            fill=normalized,
        )

        # Step 7: flush + run reconstruction.
        await session.flush()
        try:
            result = await self._engine.run(
                session,
                user_id=user_id,
                account_id=trade_row.account_id,
                instrument_id=trade_row.instrument_id,
                product_type=product_type,
                instrument_type=instrument_type,
            )
        except (ReconstructionDataError, ReconstructionConsistencyError) as exc:
            raise ReconstructionFailedError(str(exc)) from exc

        # Step 7b: if planned_stop is set, recompute planned_risk_amount with
        # updated average_entry and total_entry_quantity (BLK-3 — Dhanvantari).
        # ORDERING CONSTRAINT: flush BEFORE step 8 (backfill_all_closed).
        if trade_row.planned_stop is not None:
            # Re-fetch updated trade row (engine has flushed updated values via REQ-7).
            updated_trade = await session.get(Trade, trade_id)
            if updated_trade is not None and updated_trade.average_entry is not None:
                avg_entry = Decimal(str(updated_trade.average_entry))
                total_qty = Decimal(str(updated_trade.total_entry_quantity))
                planned_stop = Decimal(str(updated_trade.planned_stop))

                # Step 7b.b: consistency guard — validate stop is still on correct side.
                direction = updated_trade.direction
                if direction == "LONG" and planned_stop >= avg_entry:
                    raise PlannedStopWrongSideError(
                        direction,
                        "After scale-in, planned stop for LONG trade is no longer below "
                        "average entry. Planned stop is now on the wrong side.",
                    )
                if direction == "SHORT" and planned_stop <= avg_entry:
                    raise PlannedStopWrongSideError(
                        direction,
                        "After scale-in, planned stop for SHORT trade is no longer above "
                        "average entry. Planned stop is now on the wrong side.",
                    )

                # Step 7b.c: recompute planned_risk_amount.
                new_planned_risk = abs(avg_entry - planned_stop) * total_qty
                await self._trade_repo.update_trade(
                    session, trade_id, {"planned_risk_amount": new_planned_risk}
                )
                await session.flush()

        # Step 8: backfill P&L if reconstruction closed the trade.
        if result.trades_closed > 0:
            await self._pnl_service.backfill_all_closed(user_id)

        # Step 9: (caller commits) return updated trade.
        trade_final = await session.get(Trade, trade_id)
        if trade_final is None:
            raise ReconstructionFailedError(
                f"Trade {trade_id} not found after add_fill reconstruction"
            )
        return trade_final

    # -------------------------------------------------------------------------
    # soft_delete_trade — DELETE /v1/trades/{id}
    # -------------------------------------------------------------------------

    async def soft_delete_trade(self, user_id: uuid.UUID, trade_id: uuid.UUID) -> None:
        """Soft-delete a manually entered trade.

        Steps 0–7 per the execution plan. Sets is_deleted = true; does NOT
        change trade.status. The is_deleted flag is the sole deletion signal.
        Excludes all non-already-excluded fills in one batch (A-16-5).

        Domain ruling D2: only trades where all fills have import_source='MANUAL'
        may be soft-deleted. Broker-imported fills represent auditable broker
        records and must be disputed via the fill exclusion mechanism.

        R-16-4 note: if the trade has a journal entry, the journal row is not
        deleted here. The trade row still exists (FK intact), so the journal FK
        is valid. The journal entry becomes orphaned in UX terms (no trade to
        navigate to) but there is no data integrity problem. Step 19 handles
        journal visibility filtering.
        """
        session = self._session

        # Step 0: look up the trade.
        trade_row = await session.get(Trade, trade_id)
        if trade_row is None or trade_row.is_deleted:
            raise TradeNotFoundError(trade_id)

        # Step 1: ownership-only query — DO NOT use TradingAccountService.get_active()
        # (A-16-4). Account deactivation does not revoke the user's right to delete
        # their own manually entered trade. Auth boundary (BLK-2): steps 0–1 establish
        # identity BEFORE any fill data is accessed. Without this ordering, an
        # unauthenticated caller can probe fill provenance (CSV vs MANUAL) on any trade
        # UUID by observing the response code — an information-disclosure vulnerability.
        ownership_stmt = text(
            "SELECT id FROM trading_accounts WHERE id = :account_id AND user_id = :user_id"
        )
        ownership_result = await session.execute(
            ownership_stmt,
            {"account_id": str(trade_row.account_id), "user_id": str(user_id)},
        )
        if ownership_result.one_or_none() is None:
            raise TradeNotOwnedError(trade_id)

        # Step 2: fetch all fills for this trade and verify all are MANUAL (D2).
        fills_stmt = select(ExecutionFill).where(ExecutionFill.trade_id == trade_id)
        fills_result = await session.execute(fills_stmt)
        fills = list(fills_result.scalars().all())

        non_manual = [f for f in fills if f.import_source != "MANUAL"]
        if non_manual:
            raise TradeNotManualError(trade_id)

        # Step 3: batch query for already-excluded fills (A-16-5).
        # One SELECT instead of N per-fill exists_by_fill_id() calls.
        excluded_ids = await self._fill_exclusion_repo.get_excluded_fill_ids_for_trade(
            session, trade_id
        )
        fills_to_exclude = [f for f in fills if f.id not in excluded_ids]

        # AMB-02: even if fills_to_exclude is empty (all fills already excluded),
        # the DELETE still succeeds and sets is_deleted = true. The user who excluded
        # all fills one by one should still be able to soft-delete the trade shell.

        # Step 4: create exclusion records for each fill not already excluded.
        for fill in fills_to_exclude:
            await self._fill_exclusion_repo.create_exclusion(
                session,
                fill_id=fill.id,
                reason="USER_DELETED_TRADE",
                replacement_fill_ids=[],
                excluded_by=user_id,
            )

        # Step 5: set is_deleted = true. Do NOT change trade.status.
        await self._trade_repo.update_trade(session, trade_id, {"is_deleted": True})

        # Step 6: (caller commits)
        # Step 7: router returns 204 No Content.
