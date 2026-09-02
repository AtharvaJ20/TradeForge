"""Unit tests for ZerodhaAdapter.

Covers WS-5 Test Group B scenarios:
  B1  EQ fill happy path
  B2  F&O futures monthly symbol
  B3  F&O monthly option (CE/PE)
  B4  F&O weekly option (CE/PE)
  B5  product column absent + valid hint
  B6  product column absent + no hint → MissingProductTypeError
  B7  BE series → CNC (G3 ruling)
  B8  EXPIRY_SQUAREOFF detection via auction flag
  B9  EXPIRY_SQUAREOFF detection via 15:20–15:35 IST window
  B10 IST → UTC timestamp conversion
  B11 PRE_OPEN session derivation
  B12 POST_CLOSE session derivation
  B13 detect() — valid header
  B14 detect() — missing column
  B15 empty file → EmptyFileError
  B16 unrecognized file → UnrecognizedFileError
  B17 invalid price → InvalidFillError collected
  B18 negative quantity → InvalidFillError collected
  B19 CD segment → InvalidFillError collected
  B20 BSE EQ fill
  B21 unknown trade_type → InvalidFillError
  B22 product_type_hint validated
  B23 BOM-prefixed UTF-8 file
  B24 last_thursday helper — known dates
  B25 weekly option expiry is literal date in symbol (not last Thursday)
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tradeforge.domain.import_domain.errors import (
    EmptyFileError,
    MissingProductTypeError,
    UnrecognizedFileError,
)
from tradeforge.infrastructure.adapters.zerodha_adapter import (
    ZerodhaAdapter,
    _last_thursday,
    _parse_fo_symbol,
)

_IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# CSV builders
# ---------------------------------------------------------------------------

_BASE_HEADERS = [
    "symbol",
    "trade_date",
    "exchange",
    "segment",
    "series",
    "trade_type",
    "quantity",
    "price",
    "trade_id",
    "order_id",
    "order_execution_time",
    "auction",
    "product",
]


def _csv_bytes(rows: list[dict], headers: list[str] | None = None, bom: bool = False) -> bytes:
    headers = headers or _BASE_HEADERS
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    text = buf.getvalue()
    return ("﻿" + text if bom else text).encode("utf-8")


def _eq_row(**overrides) -> dict:
    base = {
        "symbol": "RELIANCE",
        "trade_date": "2024-10-15",
        "exchange": "NSE",
        "segment": "EQ",
        "series": "EQ",
        "trade_type": "buy",
        "quantity": "100",
        "price": "2500.00",
        "trade_id": "TID001",
        "order_id": "OID001",
        "order_execution_time": "2024-10-15 10:30:00",
        "auction": "no",
        "product": "CNC",
    }
    base.update(overrides)
    return base


def _fo_row(**overrides) -> dict:
    base = _eq_row()
    base.update(
        {
            "symbol": "NIFTY24OCTFUT",
            "exchange": "NSE",
            "segment": "FO",
            "series": "XX",
            "product": "NRML",
        }
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestLastThursday:
    """B24 — _last_thursday known-date verification."""

    def test_october_2024(self):
        # Oct 2024: Thu=3,10,17,24,31 → last Thu = Oct 31
        assert _last_thursday(2024, 10) == date(2024, 10, 31)

    def test_november_2024(self):
        # Nov 2024: 7,14,21,28 → last = Nov 28
        assert _last_thursday(2024, 11) == date(2024, 11, 28)

    def test_december_2024(self):
        # Dec 2024: 5,12,19,26 → last = Dec 26
        assert _last_thursday(2024, 12) == date(2024, 12, 26)

    def test_january_2025(self):
        # Jan 2025: 2,9,16,23,30 → last = Jan 30
        assert _last_thursday(2025, 1) == date(2025, 1, 30)


class TestParseFoSymbol:
    """Symbol parsing coverage for each regex branch."""

    def test_monthly_fut(self):
        result = _parse_fo_symbol("NIFTY24OCTFUT")
        assert result is not None
        base, itype, expiry, strike = result
        assert base == "NIFTY"
        assert itype == "FUT"
        assert expiry == date(2024, 10, 31)
        assert strike is None

    def test_monthly_ce(self):
        result = _parse_fo_symbol("NIFTY24OCT25000CE")
        assert result is not None
        base, itype, expiry, strike = result
        assert itype == "CE"
        assert expiry == date(2024, 10, 31)
        assert strike == Decimal("25000")

    def test_monthly_pe(self):
        result = _parse_fo_symbol("BANKNIFTY24NOV50000PE")
        assert result is not None
        base, itype, expiry, strike = result
        assert base == "BANKNIFTY"
        assert itype == "PE"
        assert expiry == date(2024, 11, 28)
        assert strike == Decimal("50000")

    def test_weekly_ce_october(self):
        # O=Oct, dd=10, NIFTY25O103500CE → Oct 10, 2025
        result = _parse_fo_symbol("NIFTY25O103500CE")
        assert result is not None
        base, itype, expiry, strike = result
        assert base == "NIFTY"
        assert itype == "CE"
        assert expiry == date(2025, 10, 10)
        assert strike == Decimal("3500")

    def test_weekly_pe_november(self):
        # N=Nov
        result = _parse_fo_symbol("NIFTY25N0623500PE")
        assert result is not None
        _base, _itype, expiry, _strike = result
        assert expiry == date(2025, 11, 6)

    def test_weekly_december(self):
        result = _parse_fo_symbol("NIFTY25D1825000CE")
        assert result is not None
        _base, _itype, expiry, _strike = result
        assert expiry == date(2025, 12, 18)

    def test_unrecognized_returns_none(self):
        assert _parse_fo_symbol("NOTACONTRACT") is None

    def test_equity_symbol_returns_none(self):
        assert _parse_fo_symbol("RELIANCE") is None


# ---------------------------------------------------------------------------
# ZerodhaAdapter.detect()
# ---------------------------------------------------------------------------


class TestZerodhaAdapterDetect:
    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def test_valid_header_detected(self):
        data = _csv_bytes([_eq_row()])
        assert self.adapter.detect(data) is True

    def test_missing_one_column_not_detected(self):
        headers = [h for h in _BASE_HEADERS if h != "order_execution_time"]
        data = _csv_bytes([_eq_row()], headers=headers)
        assert self.adapter.detect(data) is False

    def test_empty_bytes_not_detected(self):
        assert self.adapter.detect(b"") is False

    def test_random_bytes_not_detected(self):
        assert self.adapter.detect(b"\x00\x01\x02") is False

    def test_bom_prefix_detected(self):
        data = _csv_bytes([_eq_row()], bom=True)
        assert self.adapter.detect(data) is True


# ---------------------------------------------------------------------------
# ZerodhaAdapter.parse() — happy paths
# ---------------------------------------------------------------------------


class TestZerodhaAdapterParseEquity:
    """B1, B10, B11, B12, B20."""

    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def test_eq_fill_parsed(self):
        data = _csv_bytes([_eq_row()])
        result = self.adapter.parse(data)
        assert len(result.fills) == 1
        assert result.errors == []
        fill = result.fills[0]
        assert fill.symbol_raw == "RELIANCE"
        assert fill.exchange_segment == "NSE_EQ"
        assert fill.instrument_type == "EQ"
        assert fill.side == "BUY"
        assert fill.quantity == Decimal("100")
        assert fill.price == Decimal("2500.00")
        assert fill.product_type == "CNC"
        assert fill.broker == "ZERODHA"
        assert fill.import_source == "CSV"
        assert fill.is_auction is False
        assert fill.is_expiry_squareoff is False

    def test_ist_to_utc_conversion(self):
        # 10:30 IST = 05:00 UTC
        data = _csv_bytes([_eq_row(order_execution_time="2024-10-15 10:30:00")])
        result = self.adapter.parse(data)
        fill = result.fills[0]
        expected_utc = datetime(2024, 10, 15, 5, 0, 0, tzinfo=UTC)
        assert fill.fill_timestamp == expected_utc

    def test_pre_open_session(self):
        # 09:05 IST is PRE_OPEN
        data = _csv_bytes([_eq_row(order_execution_time="2024-10-15 09:05:00")])
        result = self.adapter.parse(data)
        assert result.fills[0].session == "PRE_OPEN"

    def test_regular_session(self):
        # 10:30 IST is REGULAR
        data = _csv_bytes([_eq_row(order_execution_time="2024-10-15 10:30:00")])
        result = self.adapter.parse(data)
        assert result.fills[0].session == "REGULAR"

    def test_post_close_session(self):
        # 15:50 IST is POST_CLOSE
        data = _csv_bytes([_eq_row(order_execution_time="2024-10-15 15:50:00")])
        result = self.adapter.parse(data)
        assert result.fills[0].session == "POST_CLOSE"

    def test_sell_side(self):
        data = _csv_bytes([_eq_row(trade_type="sell")])
        result = self.adapter.parse(data)
        assert result.fills[0].side == "SELL"

    def test_bse_eq_fill(self):
        data = _csv_bytes([_eq_row(exchange="BSE", segment="EQ")])
        result = self.adapter.parse(data)
        fill = result.fills[0]
        assert fill.exchange_segment == "BSE_EQ"
        assert fill.exchange == "BSE"

    def test_auction_flag_true(self):
        data = _csv_bytes([_eq_row(auction="yes")])
        result = self.adapter.parse(data)
        assert result.fills[0].is_auction is True

    def test_bom_file_parsed(self):
        data = _csv_bytes([_eq_row()], bom=True)
        result = self.adapter.parse(data)
        assert len(result.fills) == 1

    def test_total_rows_count(self):
        rows = [_eq_row(trade_id=f"T{i}") for i in range(3)]
        data = _csv_bytes(rows)
        result = self.adapter.parse(data)
        assert result.total_rows == 3


class TestZerodhaAdapterParseFO:
    """B2, B3, B4, B25."""

    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def test_futures_monthly(self):
        data = _csv_bytes([_fo_row(symbol="NIFTY24OCTFUT")])
        result = self.adapter.parse(data)
        assert len(result.fills) == 1
        fill = result.fills[0]
        assert fill.symbol_raw == "NIFTY"
        assert fill.instrument_type == "FUT"
        assert fill.expiry_date == date(2024, 10, 31)
        assert fill.strike_price is None
        assert fill.exchange_segment == "NSE_FO"
        assert fill.product_type == "NRML"

    def test_monthly_option_ce(self):
        data = _csv_bytes([_fo_row(symbol="NIFTY24OCT25000CE")])
        result = self.adapter.parse(data)
        fill = result.fills[0]
        assert fill.instrument_type == "CE"
        assert fill.strike_price == Decimal("25000")
        assert fill.expiry_date == date(2024, 10, 31)

    def test_monthly_option_pe(self):
        data = _csv_bytes([_fo_row(symbol="BANKNIFTY24OCT52000PE", trade_id="T2")])
        result = self.adapter.parse(data)
        fill = result.fills[0]
        assert fill.instrument_type == "PE"
        assert fill.strike_price == Decimal("52000")

    def test_weekly_option(self):
        # NIFTY25O103500CE → Oct 10, 2025 expiry, strike 3500, CE
        data = _csv_bytes([_fo_row(symbol="NIFTY25O103500CE", trade_id="T3")])
        result = self.adapter.parse(data)
        fill = result.fills[0]
        assert fill.instrument_type == "CE"
        assert fill.expiry_date == date(2025, 10, 10)
        assert fill.strike_price == Decimal("3500")

    def test_weekly_option_expiry_is_not_last_thursday(self):
        # Weekly options expire on the date encoded in symbol (B25)
        # Oct 10, 2025 is a Friday — not last Thursday
        data = _csv_bytes([_fo_row(symbol="NIFTY25O103500CE", trade_id="T4")])
        result = self.adapter.parse(data)
        fill = result.fills[0]
        # Last Thursday of Oct 2025 is Oct 30
        assert fill.expiry_date != _last_thursday(2025, 10)
        assert fill.expiry_date == date(2025, 10, 10)


class TestZerodhaAdapterParseExpiry:
    """B8, B9 — EXPIRY_SQUAREOFF detection."""

    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def test_auction_on_expiry_date_is_squareoff(self):
        # Expiry of NIFTY24OCTFUT = Oct 31, 2024
        data = _csv_bytes(
            [
                _fo_row(
                    symbol="NIFTY24OCTFUT",
                    trade_date="2024-10-31",
                    order_execution_time="2024-10-31 10:30:00",
                    auction="yes",
                )
            ]
        )
        result = self.adapter.parse(data)
        assert result.fills[0].is_expiry_squareoff is True

    def test_closing_window_on_expiry_date_is_squareoff(self):
        # 15:25 IST on expiry day → squareoff (input timestamp is in IST per Zerodha format)
        data = _csv_bytes(
            [
                _fo_row(
                    symbol="NIFTY24OCTFUT",
                    trade_date="2024-10-31",
                    order_execution_time="2024-10-31 15:25:00",
                    auction="no",
                )
            ]
        )
        result = self.adapter.parse(data)
        assert result.fills[0].is_expiry_squareoff is True

    def test_non_expiry_date_not_squareoff(self):
        data = _csv_bytes(
            [
                _fo_row(
                    symbol="NIFTY24OCTFUT",
                    trade_date="2024-10-15",
                    order_execution_time="2024-10-15 09:55:00",
                    auction="no",
                )
            ]
        )
        result = self.adapter.parse(data)
        assert result.fills[0].is_expiry_squareoff is False

    def test_equity_fill_never_squareoff(self):
        data = _csv_bytes([_eq_row(auction="yes")])
        result = self.adapter.parse(data)
        assert result.fills[0].is_expiry_squareoff is False


class TestZerodhaAdapterProductDerivation:
    """B5, B6, B7 — product derivation without 'product' column."""

    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def _no_product_csv(self, rows: list[dict]) -> bytes:
        headers = [h for h in _BASE_HEADERS if h != "product"]
        return _csv_bytes(rows, headers=headers)

    def test_hint_used_when_product_col_absent(self):
        data = self._no_product_csv([_fo_row()])
        result = self.adapter.parse(data, product_type_hint="MIS")
        assert result.fills[0].product_type == "MIS"

    def test_missing_product_raises_for_fo(self):
        data = self._no_product_csv([_fo_row()])
        with pytest.raises(MissingProductTypeError):
            self.adapter.parse(data)

    def test_missing_product_raises_for_eq_non_be(self):
        data = self._no_product_csv([_eq_row(series="EQ")])
        with pytest.raises(MissingProductTypeError):
            self.adapter.parse(data)

    def test_be_series_gets_cnc_without_product_col(self):
        data = self._no_product_csv([_eq_row(series="BE")])
        result = self.adapter.parse(data)
        assert result.fills[0].product_type == "CNC"

    def test_be_series_gets_cnc_regardless_of_hint(self):
        data = self._no_product_csv([_eq_row(series="BE")])
        result = self.adapter.parse(data, product_type_hint="MIS")
        assert result.fills[0].product_type == "CNC"

    def test_invalid_hint_raises_value_error(self):
        data = _csv_bytes([_fo_row()])
        with pytest.raises(ValueError, match="product_type_hint"):
            self.adapter.parse(data, product_type_hint="INVALID")


# ---------------------------------------------------------------------------
# ZerodhaAdapter.parse() — error collection
# ---------------------------------------------------------------------------


class TestZerodhaAdapterErrorCollection:
    """B17, B18, B19, B21."""

    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def test_invalid_price_collected(self):
        rows = [
            _eq_row(trade_id="T1", price="-100"),
            _eq_row(trade_id="T2"),
        ]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.fills) == 1
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "price"

    def test_zero_quantity_collected(self):
        rows = [_eq_row(quantity="0")]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "quantity"

    def test_cd_segment_collected(self):
        rows = [_eq_row(segment="CD", trade_id="T1")]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "segment"

    def test_unknown_trade_type_collected(self):
        rows = [_eq_row(trade_type="hold")]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "trade_type"

    def test_bad_date_format_collected(self):
        rows = [_eq_row(trade_date="15-10-2024")]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "trade_date"

    def test_bad_timestamp_format_collected(self):
        rows = [_eq_row(order_execution_time="10:30:00")]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.errors) == 1

    def test_unparseable_fo_symbol_collected(self):
        rows = [_fo_row(symbol="BADCONTRACT")]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "symbol"

    def test_good_rows_continue_after_bad_row(self):
        rows = [
            _eq_row(trade_id="T1", price="0"),
            _eq_row(trade_id="T2"),
            _eq_row(trade_id="T3"),
        ]
        result = self.adapter.parse(_csv_bytes(rows))
        assert len(result.fills) == 2
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# ZerodhaAdapter.parse() — structural errors
# ---------------------------------------------------------------------------


class TestZerodhaAdapterStructuralErrors:
    """B15, B16."""

    def setup_method(self):
        self.adapter = ZerodhaAdapter()

    def test_empty_file_raises(self):
        headers = _BASE_HEADERS
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        data = buf.getvalue().encode("utf-8")
        with pytest.raises(EmptyFileError):
            self.adapter.parse(data)

    def test_unrecognized_file_raises(self):
        data = b"col1,col2\n1,2\n"
        with pytest.raises(UnrecognizedFileError):
            self.adapter.parse(data)

    def test_completely_empty_bytes_raises_unrecognized(self):
        with pytest.raises(UnrecognizedFileError):
            self.adapter.parse(b"")
