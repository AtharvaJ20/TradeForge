"""Unit tests for import domain types and errors."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from tradeforge.domain.import_domain.errors import (
    AccountInactiveError,
    AccountNotFoundError,
    AdapterNotFoundError,
    DuplicateImportError,
    EmptyFileError,
    ImportDomainError,
    InstrumentNotFoundError,
    InvalidFillError,
    MissingProductTypeError,
    UnrecognizedFileError,
)
from tradeforge.domain.import_domain.types import (
    AdapterParseResult,
    ImportRecord,
    NormalizedFill,
    TradingAccount,
)

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class TestImportDomainErrors:
    def test_account_not_found_error_is_import_domain_error(self):
        err = AccountNotFoundError(uuid.uuid4())
        assert isinstance(err, ImportDomainError)

    def test_account_not_found_stores_id(self):
        uid = uuid.uuid4()
        err = AccountNotFoundError(uid)
        assert err.account_id == uid
        assert str(uid) in str(err)

    def test_account_inactive_error(self):
        uid = uuid.uuid4()
        err = AccountInactiveError(uid)
        assert err.account_id == uid
        assert isinstance(err, ImportDomainError)

    def test_duplicate_import_error(self):
        uid = uuid.uuid4()
        err = DuplicateImportError("deadbeef" * 8, uid)
        assert err.file_hash == "deadbeef" * 8
        assert err.account_id == uid
        assert "deadbeef" in str(err)

    def test_invalid_fill_error_attributes(self):
        err = InvalidFillError(7, "price", "-5.0", "Must be > 0")
        assert err.row_index == 7
        assert err.field_name == "price"
        assert err.raw_value == "-5.0"
        assert err.message == "Must be > 0"
        assert "Row 7" in str(err)
        assert "price" in str(err)

    def test_missing_product_type_uses_default_message(self):
        err = MissingProductTypeError()
        assert "product" in str(err).lower()

    def test_missing_product_type_custom_message(self):
        err = MissingProductTypeError("custom message")
        assert str(err) == "custom message"

    def test_adapter_not_found_error(self):
        err = AdapterNotFoundError("GROWW")
        assert "GROWW" in str(err)
        assert isinstance(err, ImportDomainError)

    def test_unrecognized_file_error(self):
        err = UnrecognizedFileError()
        assert isinstance(err, ImportDomainError)

    def test_empty_file_error(self):
        err = EmptyFileError()
        assert isinstance(err, ImportDomainError)

    def test_instrument_not_found_error(self):
        err = InstrumentNotFoundError("NIFTY", "NSE_FO", "FUT")
        assert err.symbol_raw == "NIFTY"
        assert err.exchange_segment == "NSE_FO"
        assert err.instrument_type == "FUT"


# ---------------------------------------------------------------------------
# NormalizedFill
# ---------------------------------------------------------------------------


def _make_fill(**kwargs) -> NormalizedFill:
    defaults = {
        "broker_trade_id": "TID001",
        "broker_order_id": "OID001",
        "broker": "ZERODHA",
        "import_source": "CSV",
        "symbol_raw": "RELIANCE",
        "exchange": "NSE",
        "exchange_segment": "NSE_EQ",
        "instrument_type": "EQ",
        "expiry_date": None,
        "strike_price": None,
        "trade_date": date(2024, 10, 15),
        "fill_timestamp": datetime(2024, 10, 15, 9, 30, 0, tzinfo=UTC),
        "session": "REGULAR",
        "side": "BUY",
        "quantity": Decimal("100"),
        "price": Decimal("2500.00"),
        "product_type": "CNC",
        "is_auction": False,
        "is_expiry_squareoff": False,
    }
    defaults.update(kwargs)
    return NormalizedFill(**defaults)


class TestNormalizedFill:
    def test_fill_is_frozen(self):
        fill = _make_fill()
        with pytest.raises((AttributeError, TypeError)):
            fill.side = "SELL"  # type: ignore[misc]

    def test_fill_equality(self):
        f1 = _make_fill()
        f2 = _make_fill()
        assert f1 == f2

    def test_fill_inequality_on_trade_id(self):
        f1 = _make_fill(broker_trade_id="T1")
        f2 = _make_fill(broker_trade_id="T2")
        assert f1 != f2

    def test_fo_fill_has_expiry_and_strike(self):
        fill = _make_fill(
            symbol_raw="NIFTY",
            exchange_segment="NSE_FO",
            instrument_type="CE",
            expiry_date=date(2024, 10, 31),
            strike_price=Decimal("25000"),
            product_type="NRML",
        )
        assert fill.expiry_date == date(2024, 10, 31)
        assert fill.strike_price == Decimal("25000")


# ---------------------------------------------------------------------------
# AdapterParseResult
# ---------------------------------------------------------------------------


class TestAdapterParseResult:
    def test_empty_result(self):
        r = AdapterParseResult()
        assert r.total_rows == 0
        assert r.fills == []
        assert r.errors == []

    def test_total_rows_counts_fills_and_errors(self):
        r = AdapterParseResult()
        r.fills.append(_make_fill())
        r.fills.append(_make_fill(broker_trade_id="T2"))
        r.errors.append(InvalidFillError(3, "price", "", "bad"))
        assert r.total_rows == 3

    def test_result_is_mutable(self):
        r = AdapterParseResult()
        fill = _make_fill()
        r.fills.append(fill)
        assert len(r.fills) == 1


# ---------------------------------------------------------------------------
# TradingAccount
# ---------------------------------------------------------------------------


class TestTradingAccount:
    def test_trading_account_is_frozen(self):
        now = datetime.now(UTC)
        ta = TradingAccount(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            broker="ZERODHA",
            display_name="My Zerodha",
            account_type="INDIVIDUAL",
            base_currency="INR",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        with pytest.raises((AttributeError, TypeError)):
            ta.status = "INACTIVE"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ImportRecord
# ---------------------------------------------------------------------------


class TestImportRecord:
    def test_import_record_is_frozen(self):
        rec = ImportRecord(
            import_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            broker="ZERODHA",
            file_hash="a" * 64,
            row_count=100,
            error_count=2,
            status="PARTIAL",
            imported_at=datetime.now(UTC),
        )
        with pytest.raises((AttributeError, TypeError)):
            rec.status = "COMPLETE"  # type: ignore[misc]
