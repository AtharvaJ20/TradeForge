"""Phase 1 Trade Reconstruction Engine.

Converts unprocessed execution_fills into trades, fill_role assignments, and
tax lots according to TRADE-RECONSTRUCTION-SPEC.md.

Out of scope — §13 unresolved areas. DO NOT implement:
  - F&O expiry handling (Unresolved 1)
  - Options exercise / assignment (Unresolved 2)
  - Corporate action adjustments (Unresolved 3)
  - Multi-lot CNC FIFO across simultaneously open trades (Unresolved 4)
  - F&O tax lot accounting / incremental NRML FIFO (Unresolved 5)

Transaction contract (caller's responsibility):
  - Provide an active AsyncSession.
  - Commit after run() returns successfully.
  - Rollback on any ReconstructionError raised by run().
  The engine acquires SELECT FOR UPDATE on the open trade at the start of run().
  All mutations within a single run() call are within the same transaction.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from tradeforge.application.pnl_service import PnlService
from tradeforge.domain.decimal_config import PRICE, QUANTITY, ZERO
from tradeforge.domain.trade.errors import (
    PositionCrossingZeroError,
    ReconstructionAmbiguityError,
    ReconstructionConsistencyError,
    ReconstructionDataError,
)
from tradeforge.domain.trade.types import (
    FillRecord,
    OpenTradeSnapshot,
    ProductTypeFamily,
    ReconstructionResult,
    direction_for_first_fill,
    fill_role_for,
    finalize_trade_type,
    product_type_family_for,
    provisional_trade_type,
)
from tradeforge.infrastructure.repositories.fill_exclusion_repo import FillExclusionRepository
from tradeforge.infrastructure.repositories.fill_repo import FillRepository
from tradeforge.infrastructure.repositories.tax_lot_repo import TaxLotRepository
from tradeforge.infrastructure.repositories.trade_repo import TradeRepository

logger = logging.getLogger(__name__)


class ReconstructionEngine:
    """Phase 1 trade reconstruction engine.

    One instance may serve many requests. All mutable state lives in local
    variables within run() — the engine itself is stateless.
    """

    def __init__(
        self,
        fill_repo: FillRepository,
        trade_repo: TradeRepository,
        tax_lot_repo: TaxLotRepository,
        fill_exclusion_repo: FillExclusionRepository,
        pnl_service: PnlService | None = None,
    ) -> None:
        self._fills = fill_repo
        self._trades = trade_repo
        self._lots = tax_lot_repo
        self._exclusions = fill_exclusion_repo
        self._pnl_service: PnlService | None = pnl_service

    async def run(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        instrument_id: uuid.UUID,
        product_type: str,
        instrument_type: str,
    ) -> ReconstructionResult:
        """Reconstruct trades for one processing unit (account, instrument, product_type_family).

        Args:
            session: Active async DB session owned by the caller.
            user_id: Owner of the fills being processed.
            account_id: Trading account whose fills are being processed.  Scopes
                both the fill query and the open-trade lock to one account so
                a user's multiple accounts never mix fills or trade state.
            instrument_id: The instrument being reconstructed.
            product_type: Raw broker product_type ('MIS', 'CNC', 'NRML').
            instrument_type: From instruments.instrument_type ('EQ', 'FUT', 'CE', 'PE').
                            Needed to disambiguate NRML_FUT vs NRML_OPT.

        Returns:
            ReconstructionResult with counts of processed fills and trades.

        Raises:
            PositionCrossingZeroError: E1 — fill crosses zero; caller must rollback.
            ReconstructionAmbiguityError: E5 — cannot order two fills deterministically.
            ReconstructionDataError: E2 — unknown enum value or family mismatch.
            ReconstructionConsistencyError: E4 — no open lot for CNC exit, or invariant
                                            assertion failed at trade close.
        """
        family = product_type_family_for(product_type)
        result = ReconstructionResult()

        # --- Step 1: lock the open trade for this processing unit (§11) ------
        open_trade = await self._trades.get_open_trade_with_lock(
            session, user_id, account_id, instrument_id, family
        )

        # --- Step 2: fetch unprocessed fills (§2 query) ----------------------
        fills = await self._fills.get_unprocessed_fills(
            session, user_id, account_id, instrument_id, product_type
        )
        if not fills:
            result.fills_skipped_no_unprocessed = 0
            return result

        # --- Step 3: E5 ambiguous-ordering check (§3 tie-breaking rule) ------
        self._check_ambiguous_ordering(fills)

        # --- Step 4: initialise running state from existing open trade --------
        if open_trade is not None:
            if open_trade.direction == "LONG":
                running_position: Decimal = open_trade.net_position
            else:
                running_position = -open_trade.net_position

            current_trade: OpenTradeSnapshot | None = open_trade
            current_trade_id: uuid.UUID | None = open_trade.id

            # Reconstruct entry accumulators from the stored average and quantity.
            entry_qty: Decimal = open_trade.total_entry_quantity
            entry_value: Decimal = open_trade.average_entry * open_trade.total_entry_quantity

            # Pre-load exit fills so average_exit at final close is complete (§9).
            if open_trade.status == "PARTIAL":
                exit_fills: list[FillRecord] = await self._fills.get_exit_fills(
                    session, open_trade.id
                )
            else:
                exit_fills = []
        else:
            running_position = ZERO
            current_trade = None
            current_trade_id = None
            entry_qty = ZERO
            entry_value = ZERO
            exit_fills = []

        # --- Step 5: process each fill in fill_timestamp order ---------------
        for fill in fills:
            # E2: validate product_type_family consistency.
            fill_family = product_type_family_for(fill.product_type)
            if fill_family != family:
                raise ReconstructionDataError(
                    f"Fill {fill.id} has product_type {fill.product_type!r} "
                    f"(family={fill_family.value}) but the processing unit expects "
                    f"family={family.value}. This is a data inconsistency."
                )

            # Compute signed delta (+qty for BUY, -qty for SELL).
            delta: Decimal = fill.quantity if fill.side == "BUY" else -fill.quantity
            new_position: Decimal = running_position + delta

            # E1: position crossing zero (§12).
            if (running_position > ZERO and new_position < ZERO) or (
                running_position < ZERO and new_position > ZERO
            ):
                raise PositionCrossingZeroError(fill.id)

            # ----------------------------------------------------------------
            # Determine fill_role and apply state machine transition (§4, §7).
            # ----------------------------------------------------------------
            if current_trade is None:
                # FLAT → OPEN: open a new trade.
                direction = direction_for_first_fill(fill.side)
                trade_type = provisional_trade_type(family, instrument_type)
                trade_id = uuid.uuid4()
                avg_entry = fill.price.quantize(*PRICE)
                qty = fill.quantity.quantize(*QUANTITY)

                await self._trades.create_trade(
                    session,
                    pk=trade_id,
                    user_id=user_id,
                    account_id=fill.account_id,
                    instrument_id=instrument_id,
                    trade_type=trade_type,
                    direction=direction,
                    status="OPEN",
                    trade_date=fill.trade_date,
                    first_fill_at=fill.fill_timestamp,
                    total_entry_quantity=qty,
                    total_exit_quantity=ZERO,
                    net_position=qty,
                    average_entry=avg_entry,
                )
                # Create the aggregated tax lot for CNC trades (§10).
                if family == ProductTypeFamily.DELIVERY:
                    await self._lots.create_lot(
                        session,
                        pk=uuid.uuid4(),
                        trade_id=trade_id,
                        user_id=user_id,
                        instrument_id=instrument_id,
                        purchase_date=fill.trade_date,
                        quantity_original=qty,
                        quantity_remaining=qty,
                        cost_per_share=avg_entry,
                    )
                    result.tax_lots_created += 1

                fill_role = fill_role_for(direction, fill.side)
                current_trade_id = trade_id
                current_trade = OpenTradeSnapshot(
                    id=trade_id,
                    direction=direction,
                    status="OPEN",
                    trade_date=fill.trade_date,
                    first_fill_at=fill.fill_timestamp,
                    total_entry_quantity=fill.quantity,
                    total_exit_quantity=ZERO,
                    net_position=fill.quantity,
                    average_entry=avg_entry,
                    trade_type=trade_type,
                )
                entry_value = fill.quantity * fill.price
                entry_qty = fill.quantity
                exit_fills = []
                result.trades_opened += 1

            else:
                # Continuing an existing trade — determine fill_role.
                direction = current_trade.direction
                fill_role = fill_role_for(direction, fill.side)
                trade_id = current_trade_id  # type: ignore[assignment]
                if trade_id is None:  # pragma: no cover
                    raise ReconstructionDataError(
                        "trade_id is None while current_trade is set — programming error"
                    )

                if fill_role == "ENTRY":
                    # Scale-in (§9 — average_entry recomputed on each ENTRY fill).
                    entry_value = entry_value + fill.quantity * fill.price
                    entry_qty = entry_qty + fill.quantity
                    new_avg_entry = (entry_value / entry_qty).quantize(*PRICE)
                    new_total_entry = (current_trade.total_entry_quantity + fill.quantity).quantize(
                        *QUANTITY
                    )
                    new_net = (current_trade.net_position + fill.quantity).quantize(*QUANTITY)
                    new_status = "PARTIAL" if current_trade.total_exit_quantity > ZERO else "OPEN"

                    await self._trades.update_trade(
                        session,
                        trade_id,
                        {
                            "total_entry_quantity": new_total_entry,
                            "net_position": new_net,
                            "average_entry": new_avg_entry,
                            "status": new_status,
                        },
                    )

                    # Update the tax lot on CNC scale-in (§10).
                    if family == ProductTypeFamily.DELIVERY:
                        await self._update_lot_on_scale_in(
                            session, trade_id, fill.quantity, new_avg_entry, result
                        )

                    current_trade = OpenTradeSnapshot(
                        id=current_trade.id,
                        direction=direction,
                        status=new_status,
                        trade_date=current_trade.trade_date,
                        first_fill_at=current_trade.first_fill_at,
                        total_entry_quantity=new_total_entry,
                        total_exit_quantity=current_trade.total_exit_quantity,
                        net_position=new_net,
                        average_entry=new_avg_entry,
                        trade_type=current_trade.trade_type,
                    )

                else:
                    # EXIT fill (partial or full).
                    exit_fills.append(fill)
                    new_total_exit = (current_trade.total_exit_quantity + fill.quantity).quantize(
                        *QUANTITY
                    )
                    new_net = (current_trade.net_position - fill.quantity).quantize(*QUANTITY)

                    # Decrement tax lot for CNC exit fills (§10).
                    if family == ProductTypeFamily.DELIVERY:
                        await self._decrement_lot_on_exit(
                            session, user_id, instrument_id, fill, result
                        )

                    if new_net == ZERO:
                        # Full exit — trade closes (§5, §8, §9).
                        avg_exit = self._compute_average_exit(exit_fills).quantize(*PRICE)
                        final_trade_type = finalize_trade_type(
                            current_trade.trade_type,
                            current_trade.trade_date,
                            fill.trade_date,
                        )
                        await self._trades.update_trade(
                            session,
                            trade_id,
                            {
                                "status": "CLOSED",
                                "last_fill_at": fill.fill_timestamp,
                                "average_exit": avg_exit,
                                "net_position": ZERO,
                                "total_exit_quantity": new_total_exit,
                                "trade_type": final_trade_type,
                            },
                        )

                        # Assert tax lot consistency at close (§10).
                        if family == ProductTypeFamily.DELIVERY:
                            await self._assert_lot_closed(session, trade_id, fill)

                        # Reset local state — next fill opens a new trade.
                        current_trade = None
                        current_trade_id = None
                        entry_value = ZERO
                        entry_qty = ZERO
                        exit_fills = []
                        result.trades_closed += 1

                        # Trigger P&L calculation for the just-closed trade.
                        if self._pnl_service is not None:
                            from tradeforge.domain.pnl.errors import ChargeScheduleNotFoundError

                            try:
                                await self._pnl_service.calculate_and_store(trade_id, user_id)
                            except ChargeScheduleNotFoundError as exc:
                                logger.warning("P&L skipped for trade %s: %s", trade_id, exc)

                    else:
                        # Partial exit.
                        await self._trades.update_trade(
                            session,
                            trade_id,
                            {
                                "status": "PARTIAL",
                                "last_fill_at": fill.fill_timestamp,
                                "total_exit_quantity": new_total_exit,
                                "net_position": new_net,
                            },
                        )
                        current_trade = OpenTradeSnapshot(
                            id=current_trade.id,
                            direction=direction,
                            status="PARTIAL",
                            trade_date=current_trade.trade_date,
                            first_fill_at=current_trade.first_fill_at,
                            total_entry_quantity=current_trade.total_entry_quantity,
                            total_exit_quantity=new_total_exit,
                            net_position=new_net,
                            average_entry=current_trade.average_entry,
                            trade_type=current_trade.trade_type,
                        )

            # Atomic fill assignment — trade_id + fill_role together (§7).
            await self._fills.assign_trade(session, fill.id, trade_id, fill_role)
            running_position = new_position
            result.fills_processed += 1

        # Flush all pending changes before returning to the caller.
        await session.flush()
        return result

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _update_lot_on_scale_in(
        self,
        session: AsyncSession,
        trade_id: uuid.UUID,
        scale_in_qty: Decimal,
        new_avg_entry: Decimal,
        result: ReconstructionResult,
    ) -> None:
        """Update tax lot quantities and cost_per_share on a CNC scale-in (§10)."""
        lot = await self._lots.get_lot_for_trade(session, trade_id)
        if lot is None:
            raise ReconstructionConsistencyError(
                f"E4: No tax lot found for CNC trade {trade_id} during scale-in. "
                "Manual lot reconciliation required."
            )
        qty_already_exited = Decimal(str(lot.quantity_original)) - Decimal(
            str(lot.quantity_remaining)
        )
        new_qty_original = (Decimal(str(lot.quantity_original)) + scale_in_qty).quantize(*QUANTITY)
        new_qty_remaining = (new_qty_original - qty_already_exited).quantize(*QUANTITY)
        await self._lots.update_lot(
            session,
            lot.id,
            {
                "quantity_original": new_qty_original,
                "quantity_remaining": new_qty_remaining,
                "cost_per_share": new_avg_entry,
            },
        )
        result.tax_lots_updated += 1

    async def _decrement_lot_on_exit(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        fill: FillRecord,
        result: ReconstructionResult,
    ) -> None:
        """Decrement the open tax lot when a CNC EXIT fill is processed (§10, E4 check)."""
        lot = await self._lots.get_open_lot(session, user_id, instrument_id)
        if lot is None:
            raise ReconstructionConsistencyError(
                f"E4: No open tax lot found for user={user_id}, "
                f"instrument={instrument_id} when processing CNC exit fill {fill.id}. "
                "Manual lot reconciliation required."
            )

        new_remaining = (Decimal(str(lot.quantity_remaining)) - fill.quantity).quantize(*QUANTITY)

        if new_remaining < ZERO:
            raise ReconstructionConsistencyError(
                f"E4: Tax lot {lot.id} quantity_remaining would become negative "
                f"({new_remaining}) after exit fill {fill.id}. "
                "Manual lot reconciliation required."
            )

        new_lot_status = "CLOSED" if new_remaining == ZERO else "PARTIALLY_CLOSED"
        await self._lots.update_lot(
            session,
            lot.id,
            {"quantity_remaining": new_remaining, "status": new_lot_status},
        )
        result.tax_lots_updated += 1

    async def _assert_lot_closed(
        self,
        session: AsyncSession,
        trade_id: uuid.UUID,
        fill: FillRecord,
    ) -> None:
        """Assert that the tax lot for a closing CNC trade is CLOSED (§10).

        If the lot still has quantity_remaining > 0 after the trade closes, the
        reconstruction is in an inconsistent state and the engine raises E4.
        """
        lot = await self._lots.get_lot_for_trade(session, trade_id)
        if lot is None:
            return  # no lot found — already caught by _decrement_lot_on_exit
        remaining = Decimal(str(lot.quantity_remaining))
        if remaining != ZERO or lot.status != "CLOSED":
            raise ReconstructionConsistencyError(
                f"E4: Tax lot {lot.id} for trade {trade_id} has "
                f"quantity_remaining={remaining}, status={lot.status!r} "
                f"after trade close triggered by fill {fill.id}. "
                "Expected quantity_remaining=0, status='CLOSED'."
            )

    @staticmethod
    def _compute_average_exit(exit_fills: list[FillRecord]) -> Decimal:
        """Weighted average price of all exit fills (§9 average_exit formula).

        Returns full Decimal precision — caller must quantize to PRICE.
        """
        if not exit_fills:
            return ZERO
        total_value = sum(f.quantity * f.price for f in exit_fills)
        total_qty = sum(f.quantity for f in exit_fills)
        return total_value / total_qty  # type: ignore[return-value]

    @staticmethod
    def _check_ambiguous_ordering(fills: list[FillRecord]) -> None:
        """E5: detect fills with identical fill_timestamp and no deterministic tiebreaker.

        The tie-breaking order is: fill_timestamp → fill_id → created_at (§3).
        If all three are equal, the engine cannot guarantee deterministic output
        and raises ReconstructionAmbiguityError.
        """
        for i in range(len(fills) - 1):
            a = fills[i]
            b = fills[i + 1]
            if (
                a.fill_timestamp == b.fill_timestamp
                and a.fill_id_str is None
                and b.fill_id_str is None
                and a.created_at == b.created_at
            ):
                raise ReconstructionAmbiguityError(a.id, b.id)
