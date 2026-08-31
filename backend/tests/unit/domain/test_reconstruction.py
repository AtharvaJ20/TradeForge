"""Unit tests for the trade reconstruction domain layer.

Pure domain logic only: no I/O, no database, no async. Tests the helpers in
domain/trade/types.py, domain/trade/errors.py, and the static helpers on
ReconstructionEngine.

Run with:
    cd backend && pytest tests/unit/domain/test_reconstruction.py -v
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from tradeforge.application.trade.reconstruction import ReconstructionEngine
from tradeforge.domain.trade.errors import (
    PositionCrossingZeroError,
    ReconstructionAmbiguityError,
    ReconstructionConsistencyError,
    ReconstructionDataError,
)
from tradeforge.domain.trade.types import (
    FillRecord,
    ProductTypeFamily,
    direction_for_first_fill,
    fill_role_for,
    finalize_trade_type,
    product_type_family_for,
    provisional_trade_type,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2026, 1, 15, 9, 31, 0, tzinfo=timezone.utc)
_DATE = date(2026, 1, 15)


def _fill(
    *,
    side: str = "BUY",
    quantity: str = "100",
    price: str = "250.00",
    product_type: str = "MIS",
    fill_id_str: str | None = "F001",
    ts_offset_seconds: int = 0,
    created_at_offset_seconds: int = 0,
    trade_id: uuid.UUID | None = None,
) -> FillRecord:
    ts = datetime(2026, 1, 15, 9, 31, ts_offset_seconds, tzinfo=timezone.utc)
    created = datetime(2026, 1, 15, 9, 30, created_at_offset_seconds, tzinfo=timezone.utc)
    return FillRecord(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        trade_id=trade_id,
        fill_timestamp=ts,
        trade_date=_DATE,
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        product_type=product_type,
        fill_id_str=fill_id_str,
        created_at=created,
        import_source="BROKER",
    )


# ---------------------------------------------------------------------------
# product_type_family_for
# ---------------------------------------------------------------------------


def test_product_type_family_mis() -> None:
    assert product_type_family_for("MIS") == ProductTypeFamily.INTRADAY


def test_product_type_family_cnc() -> None:
    assert product_type_family_for("CNC") == ProductTypeFamily.DELIVERY


def test_product_type_family_nrml() -> None:
    assert product_type_family_for("NRML") == ProductTypeFamily.FO


def test_product_type_family_unknown() -> None:
    with pytest.raises(ReconstructionDataError, match="Unknown product_type"):
        product_type_family_for("BOGUS")


# ---------------------------------------------------------------------------
# provisional_trade_type
# ---------------------------------------------------------------------------


def test_provisional_mis() -> None:
    assert provisional_trade_type(ProductTypeFamily.INTRADAY, "EQ") == "MIS"


def test_provisional_cnc() -> None:
    assert provisional_trade_type(ProductTypeFamily.DELIVERY, "EQ") == "CNC"


def test_provisional_nrml_fut() -> None:
    assert provisional_trade_type(ProductTypeFamily.FO, "FUT") == "NRML_FUT"


def test_provisional_nrml_ce() -> None:
    assert provisional_trade_type(ProductTypeFamily.FO, "CE") == "NRML_OPT"


def test_provisional_nrml_pe() -> None:
    assert provisional_trade_type(ProductTypeFamily.FO, "PE") == "NRML_OPT"


def test_provisional_fo_unknown_instrument() -> None:
    with pytest.raises(ReconstructionDataError, match="Unknown instrument_type"):
        provisional_trade_type(ProductTypeFamily.FO, "EQ")


# ---------------------------------------------------------------------------
# finalize_trade_type
# ---------------------------------------------------------------------------


def test_finalize_cnc_same_day() -> None:
    d = date(2026, 1, 15)
    assert finalize_trade_type("CNC", d, d) == "CNC_SAME_DAY"


def test_finalize_cnc_overnight() -> None:
    assert finalize_trade_type("CNC", date(2026, 1, 15), date(2026, 1, 16)) == "CNC"


def test_finalize_mis_unchanged() -> None:
    d = date(2026, 1, 15)
    assert finalize_trade_type("MIS", d, d) == "MIS"


def test_finalize_nrml_fut_unchanged() -> None:
    d = date(2026, 1, 15)
    assert finalize_trade_type("NRML_FUT", d, d) == "NRML_FUT"


def test_finalize_nrml_opt_unchanged() -> None:
    d = date(2026, 1, 15)
    assert finalize_trade_type("NRML_OPT", d, d) == "NRML_OPT"


# ---------------------------------------------------------------------------
# fill_role_for
# ---------------------------------------------------------------------------


def test_fill_role_long_buy() -> None:
    assert fill_role_for("LONG", "BUY") == "ENTRY"


def test_fill_role_long_sell() -> None:
    assert fill_role_for("LONG", "SELL") == "EXIT"


def test_fill_role_short_sell() -> None:
    assert fill_role_for("SHORT", "SELL") == "ENTRY"


def test_fill_role_short_buy() -> None:
    assert fill_role_for("SHORT", "BUY") == "EXIT"


def test_fill_role_invalid() -> None:
    with pytest.raises(ReconstructionDataError, match="Invalid direction/side"):
        fill_role_for("LONG", "HOLD")


# ---------------------------------------------------------------------------
# direction_for_first_fill
# ---------------------------------------------------------------------------


def test_direction_buy_is_long() -> None:
    assert direction_for_first_fill("BUY") == "LONG"


def test_direction_sell_is_short() -> None:
    assert direction_for_first_fill("SELL") == "SHORT"


def test_direction_unknown_side() -> None:
    with pytest.raises(ReconstructionDataError, match="Unknown fill side"):
        direction_for_first_fill("HOLD")


# ---------------------------------------------------------------------------
# ReconstructionEngine._check_ambiguous_ordering (E5)
# ---------------------------------------------------------------------------


def test_no_ambiguity_different_timestamps() -> None:
    f1 = _fill(ts_offset_seconds=0, fill_id_str=None)
    f2 = _fill(ts_offset_seconds=1, fill_id_str=None)
    # Should not raise — different timestamps.
    ReconstructionEngine._check_ambiguous_ordering([f1, f2])


def test_no_ambiguity_same_timestamp_fill_ids_resolve() -> None:
    f1 = _fill(ts_offset_seconds=0, fill_id_str="F001")
    f2 = _fill(ts_offset_seconds=0, fill_id_str="F002")
    # Should not raise — fill_id differentiates.
    ReconstructionEngine._check_ambiguous_ordering([f1, f2])


def test_no_ambiguity_same_timestamp_null_fill_id_created_at_resolves() -> None:
    f1 = _fill(ts_offset_seconds=0, fill_id_str=None, created_at_offset_seconds=0)
    f2 = _fill(ts_offset_seconds=0, fill_id_str=None, created_at_offset_seconds=1)
    # Should not raise — different created_at.
    ReconstructionEngine._check_ambiguous_ordering([f1, f2])


def test_ambiguity_raises_e5() -> None:
    # Same fill_timestamp AND both fill_id NULL AND same created_at → E5.
    f1 = _fill(ts_offset_seconds=0, fill_id_str=None, created_at_offset_seconds=0)
    f2 = _fill(ts_offset_seconds=0, fill_id_str=None, created_at_offset_seconds=0)
    # Force both fills to have identical timestamps and created_at:
    shared_ts = datetime(2026, 1, 15, 9, 31, 0, tzinfo=timezone.utc)
    shared_created = datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc)
    f1 = FillRecord(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        trade_id=None,
        fill_timestamp=shared_ts,
        trade_date=_DATE,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("250.00"),
        product_type="MIS",
        fill_id_str=None,
        created_at=shared_created,
        import_source="MANUAL",
    )
    f2 = FillRecord(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        trade_id=None,
        fill_timestamp=shared_ts,
        trade_date=_DATE,
        side="BUY",
        quantity=Decimal("50"),
        price=Decimal("251.00"),
        product_type="MIS",
        fill_id_str=None,
        created_at=shared_created,
        import_source="MANUAL",
    )
    with pytest.raises(ReconstructionAmbiguityError) as exc_info:
        ReconstructionEngine._check_ambiguous_ordering([f1, f2])
    assert exc_info.value.fill_a_id == f1.id
    assert exc_info.value.fill_b_id == f2.id


# ---------------------------------------------------------------------------
# ReconstructionEngine._compute_average_exit
# ---------------------------------------------------------------------------


def test_average_exit_single_fill() -> None:
    f = _fill(side="SELL", quantity="100", price="260.00")
    avg = ReconstructionEngine._compute_average_exit([f])
    assert avg == Decimal("260.00")


def test_average_exit_two_fills() -> None:
    f1 = _fill(side="SELL", quantity="100", price="260.00")
    f2 = _fill(side="SELL", quantity="100", price="262.00")
    avg = ReconstructionEngine._compute_average_exit([f1, f2])
    # (100×260 + 100×262) / 200 = 261.00
    assert avg == Decimal("261.00")


def test_average_exit_weighted() -> None:
    f1 = _fill(side="SELL", quantity="100", price="260.00")
    f2 = _fill(side="SELL", quantity="200", price="264.00")
    avg = ReconstructionEngine._compute_average_exit([f1, f2])
    # (100×260 + 200×264) / 300 = (26000 + 52800) / 300 = 78800 / 300 ≈ 262.6667
    expected = Decimal("78800") / Decimal("300")
    assert avg == expected


def test_average_exit_empty_returns_zero() -> None:
    from tradeforge.domain.decimal_config import ZERO

    assert ReconstructionEngine._compute_average_exit([]) == ZERO


# ---------------------------------------------------------------------------
# Error class behaviour
# ---------------------------------------------------------------------------


def test_position_crossing_zero_error_captures_fill_id() -> None:
    fid = uuid.uuid4()
    err = PositionCrossingZeroError(fid)
    assert err.fill_id == fid
    assert str(fid) in str(err)


def test_reconstruction_consistency_error_is_reconstruction_error() -> None:
    from tradeforge.domain.trade.errors import ReconstructionError

    err = ReconstructionConsistencyError("tax lot inconsistency")
    assert isinstance(err, ReconstructionError)
