"""ZerodhaAdapter — BrokerAdapterPort implementation for Zerodha tradebook CSV.

Implements the NormalizedFill contract defined in NORMALIZED-FILL-CONTRACT.md.
Ganesha domain rulings G1-G4 (2026-09-01) are incorporated:
  G1: EXPIRY_SQUAREOFF is a valid exit_type — is_expiry_squareoff flag used.
  G2: PRE_OPEN fills processed identically to REGULAR by reconstruction engine.
  G3: series=BE → product_type=CNC is structural (MIS orders broker-blocked).
  G4: FO segment cannot default to NRML; product_type_hint required.

Note on §1.4 example:
  The NORMALIZED-FILL-CONTRACT.md example shows "NIFTY2510123500CE → expiry 25-Oct".
  Per the written spec, weekly options use YYMDD format where Oct=O, Nov=N, Dec=D.
  The symbol for a NIFTY Oct-12-2025 weekly option, strike 3500 CE would therefore
  be NIFTY25O123500CE.  The discrepancy in the example appears to be a typo.
  This implementation follows the written YYMDD specification.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from tradeforge.domain.import_domain.errors import (
    EmptyFileError,
    InvalidFillError,
    MissingProductTypeError,
    UnrecognizedFileError,
)
from tradeforge.domain.import_domain.types import AdapterParseResult, NormalizedFill

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_IST = timezone(timedelta(hours=5, minutes=30))
_BROKER = "ZERODHA"
_IMPORT_SOURCE = "CSV"

_REQUIRED_DETECT_COLUMNS: frozenset[str] = frozenset(
    {
        "symbol",
        "trade_date",
        "exchange",
        "segment",
        "trade_type",
        "quantity",
        "price",
        "trade_id",
        "order_id",
        "order_execution_time",
    }
)

_VALID_PRODUCT_HINTS: frozenset[str] = frozenset({"MIS", "CNC", "NRML"})
_VALID_PRODUCT_CSV: frozenset[str] = frozenset({"MIS", "CNC", "NRML"})

_MONTH_ABBR: dict[str, int] = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

# Single-char compact month codes for weekly options (1-9, O=Oct, N=Nov, D=Dec)
_COMPACT_MONTH: dict[str, int] = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "O": 10,
    "N": 11,
    "D": 12,
}

# F&O symbol regexes (applied in order: FUT → monthly OPT → weekly OPT)
_MONTH_GROUP = "(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
_FUT_RE = re.compile(rf"^([A-Z0-9]+?)(\d{{2}})({_MONTH_GROUP})FUT$")
_MONTHLY_OPT_RE = re.compile(rf"^([A-Z0-9]+?)(\d{{2}})({_MONTH_GROUP})(\d+)(CE|PE)$")
_WEEKLY_OPT_RE = re.compile(r"^([A-Z0-9]+?)(\d{2})([1-9OND])(\d{2})(\d+)(CE|PE)$")

# exchange+segment → exchange_segment mapping
_EXCHANGE_SEGMENT: dict[tuple[str, str], str] = {
    ("NSE", "EQ"): "NSE_EQ",
    ("NSE", "FO"): "NSE_FO",
    ("BSE", "EQ"): "BSE_EQ",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _last_thursday(year: int, month: int) -> date:
    """Return the last Thursday of the given month (expiry for monthly F&O)."""
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    # weekday(): Mon=0 … Thu=3
    days_back = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=days_back)


def _parse_ist_timestamp(raw: str) -> datetime:
    """Parse a Zerodha 'YYYY-MM-DD HH:MM:SS' timestamp (IST) and return UTC-aware datetime."""
    naive = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S")
    ist_aware = naive.replace(tzinfo=_IST)
    return ist_aware.astimezone(UTC)


def _derive_session(fill_ts_utc: datetime) -> str:
    """Derive session from the IST time component of the fill timestamp (§3.2)."""
    ist_dt = fill_ts_utc.astimezone(_IST)
    t = ist_dt.time()
    if (9, 0, 0) <= (t.hour, t.minute, t.second) <= (9, 14, 59):
        return "PRE_OPEN"
    if (9, 15, 0) <= (t.hour, t.minute, t.second) <= (15, 39, 59):
        return "REGULAR"
    if (15, 40, 0) <= (t.hour, t.minute, t.second) <= (16, 0, 0):
        return "POST_CLOSE"
    return "REGULAR"  # fallback per §3.2


def _parse_fo_symbol(
    symbol: str,
) -> tuple[str, str, date | None, Decimal | None] | None:
    """Parse a Zerodha F&O symbol into (base_symbol, instrument_type, expiry_date, strike_price).

    Returns None if the symbol does not match any known F&O format.
    """
    upper = symbol.upper()

    # 1. Futures
    m = _FUT_RE.match(upper)
    if m:
        base, yy, mmm = m.group(1), m.group(2), m.group(3)
        year = 2000 + int(yy)
        month = _MONTH_ABBR[mmm]
        expiry = _last_thursday(year, month)
        return base, "FUT", expiry, None

    # 2. Monthly options
    m = _MONTHLY_OPT_RE.match(upper)
    if m:
        base, yy, mmm, strike_str, opt_type = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
            m.group(5),
        )
        year = 2000 + int(yy)
        month = _MONTH_ABBR[mmm]
        expiry = _last_thursday(year, month)
        strike = Decimal(strike_str)
        return base, opt_type, expiry, strike

    # 3. Weekly options (YYMDD format — §1.4)
    m = _WEEKLY_OPT_RE.match(upper)
    if m:
        base, yy, m_code, dd, strike_str, opt_type = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
            m.group(5),
            m.group(6),
        )
        year = 2000 + int(yy)
        month = _COMPACT_MONTH[m_code]
        day = int(dd)
        expiry = date(year, month, day)
        strike = Decimal(strike_str)
        return base, opt_type, expiry, strike

    return None


def _needs_product_hint(segment: str, series: str) -> bool:
    """Return True if a row with absent 'product' column requires a product_type_hint."""
    if segment == "FO":
        return True
    if segment == "EQ" and series.upper() != "BE":
        return True
    return False


# ---------------------------------------------------------------------------
# ZerodhaAdapter
# ---------------------------------------------------------------------------


class ZerodhaAdapter:
    """Parses Zerodha tradebook CSV exports into NormalizedFill value objects.

    Satisfies BrokerAdapterPort (structural subtyping — no explicit inheritance).
    """

    def detect(self, file_content: bytes) -> bool:
        """Return True if the file header contains all required Zerodha columns."""
        try:
            text = file_content.decode("utf-8-sig").lstrip()
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames is None:
                return False
            headers = {h.strip().lower() for h in reader.fieldnames if h}
            return _REQUIRED_DETECT_COLUMNS <= headers
        except Exception:  # noqa: BLE001
            return False

    def parse(
        self,
        file_content: bytes,
        product_type_hint: str | None = None,
    ) -> AdapterParseResult:
        """Parse Zerodha tradebook CSV into NormalizedFill objects.

        Raises:
            UnrecognizedFileError: file does not match Zerodha format.
            EmptyFileError: header present but zero data rows.
            MissingProductTypeError: 'product' column absent, hint not provided,
                and at least one row requires classification.
        """
        if not self.detect(file_content):
            raise UnrecognizedFileError()

        if product_type_hint is not None and product_type_hint not in _VALID_PRODUCT_HINTS:
            raise ValueError(
                f"Invalid product_type_hint {product_type_hint!r}. "
                f"Must be one of {sorted(_VALID_PRODUCT_HINTS)}"
            )

        text = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)

        if not rows:
            raise EmptyFileError()

        # Normalise column names (strip whitespace)
        rows = [{k.strip(): v.strip() for k, v in row.items()} for row in rows]

        has_product_col = "product" in {k.lower() for k in (rows[0] if rows else {})}

        # Pre-scan: if product column is absent and no hint, check whether any
        # row would require classification → raise MissingProductTypeError.
        if not has_product_col and product_type_hint is None:
            for row in rows:
                segment = row.get("segment", "").upper()
                series = row.get("series", "").upper()
                if segment == "CD":
                    continue  # rejected later but not a hint issue
                if _needs_product_hint(segment, series):
                    raise MissingProductTypeError()

        result = AdapterParseResult()

        for row_idx, row in enumerate(rows, start=1):
            try:
                fill = self._parse_row(row, row_idx, has_product_col, product_type_hint)
                result.fills.append(fill)
            except InvalidFillError as exc:
                result.errors.append(exc)

        return result

    # ------------------------------------------------------------------
    # Row parsing
    # ------------------------------------------------------------------

    def _parse_row(  # noqa: PLR0912,PLR0915
        self,
        row: dict[str, str],
        row_idx: int,
        has_product_col: bool,
        product_type_hint: str | None,
    ) -> NormalizedFill:
        """Parse one CSV row into a NormalizedFill.  Raises InvalidFillError on failure."""

        def bad(field: str, value: str, msg: str) -> InvalidFillError:
            return InvalidFillError(row_idx, field, value, msg)

        # --- Required string fields ---
        symbol_raw = self._require(row, "symbol", row_idx).upper()
        trade_id_str = self._require(row, "trade_id", row_idx)
        order_id_str = self._require(row, "order_id", row_idx)
        exchange_raw = self._require(row, "exchange", row_idx).upper()
        segment_raw = self._require(row, "segment", row_idx).upper()
        series_raw = row.get("series", "").strip().upper()
        trade_type_raw = self._require(row, "trade_type", row_idx).lower()
        auction_raw = self._require(row, "auction", row_idx).lower()
        trade_date_str = self._require(row, "trade_date", row_idx)
        ts_str = self._require(row, "order_execution_time", row_idx)
        qty_str = self._require(row, "quantity", row_idx)
        price_str = self._require(row, "price", row_idx)

        # --- CD segment: reject and continue ---
        if segment_raw == "CD":
            raise bad("segment", segment_raw, "CD segment not supported in Phase 1")

        # --- exchange_segment ---
        es_key = (exchange_raw, segment_raw)
        if es_key not in _EXCHANGE_SEGMENT:
            if exchange_raw == "BSE" and segment_raw == "FO":
                raise bad(
                    "exchange+segment",
                    f"{exchange_raw}+{segment_raw}",
                    "BSE FO not supported",
                )
            raise bad(
                "exchange",
                exchange_raw,
                f"Unknown exchange/segment: {exchange_raw}/{segment_raw}",
            )
        exchange_segment = _EXCHANGE_SEGMENT[es_key]

        # --- trade_date ---
        try:
            trade_date = date.fromisoformat(trade_date_str)
        except ValueError:
            raise bad("trade_date", trade_date_str, "Expected YYYY-MM-DD") from None

        # --- fill_timestamp (IST → UTC) ---
        try:
            fill_timestamp = _parse_ist_timestamp(ts_str)
        except ValueError:
            raise bad("order_execution_time", ts_str, "Expected YYYY-MM-DD HH:MM:SS") from None

        # --- session ---
        session = _derive_session(fill_timestamp)
        ist_time = fill_timestamp.astimezone(_IST).time()
        if not ((9, 0, 0) <= (ist_time.hour, ist_time.minute, ist_time.second) <= (16, 0, 0)):
            logger.warning(
                "Row %d: fill_timestamp IST %s is outside market hours — defaulting to REGULAR",
                row_idx,
                ist_time,
            )

        # --- side ---
        if trade_type_raw == "buy":
            side = "BUY"
        elif trade_type_raw == "sell":
            side = "SELL"
        else:
            raise bad("trade_type", trade_type_raw, f"Unknown trade_type: {trade_type_raw!r}")

        # --- quantity ---
        try:
            qty_int = int(qty_str)
        except ValueError:
            raise bad("quantity", qty_str, "Must be a positive integer") from None
        if qty_int <= 0:
            raise bad("quantity", qty_str, "Must be > 0")
        quantity = Decimal(qty_int)

        # --- price ---
        try:
            price = Decimal(price_str)
        except InvalidOperation:
            raise bad("price", price_str, "Must be a valid decimal number") from None
        if price <= 0:
            raise bad("price", price_str, "Must be > 0")

        # --- product_type ---
        if has_product_col:
            product_csv = row.get("product", "").strip().upper()
            if product_csv not in _VALID_PRODUCT_CSV:
                raise bad("product", product_csv, f"Unknown product code: {product_csv!r}")
            product_type = product_csv
        else:
            # Derivation table per §3.4 (G3, G4 rulings applied)
            if segment_raw == "EQ" and series_raw == "BE":
                product_type = "CNC"  # structural per G3
            elif product_type_hint is not None:
                product_type = product_type_hint
            else:
                # Should not be reached — pre-scan raises MissingProductTypeError first
                raise bad(
                    "product",
                    "",
                    "product column absent and no product_type_hint provided",
                )

        # --- instrument components ---
        if segment_raw == "EQ":
            instrument_type = "EQ"
            expiry_date: date | None = None
            strike_price: Decimal | None = None
        elif segment_raw == "FO":
            parsed = _parse_fo_symbol(symbol_raw)
            if parsed is None:
                raise bad(
                    "symbol",
                    symbol_raw,
                    f"Cannot parse F&O symbol: {symbol_raw!r}",
                )
            base_sym, instrument_type, expiry_date, strike_price = parsed
            symbol_raw = base_sym  # strip contract suffix from symbol_raw
        else:
            raise bad("segment", segment_raw, f"Unsupported segment: {segment_raw!r}")

        if instrument_type not in ("EQ", "FUT", "CE", "PE"):
            raise bad(
                "symbol",
                symbol_raw,
                f"Unsupported instrument type: {instrument_type!r}",
            )

        # --- is_auction ---
        is_auction = auction_raw == "yes"

        # --- is_expiry_squareoff (§3.5) ---
        is_expiry_squareoff = False
        if segment_raw == "FO" and expiry_date is not None and trade_date == expiry_date:
            if is_auction:
                is_expiry_squareoff = True
            else:
                # Secondary: 15:20–15:35 IST closing window
                t = ist_time
                if (15, 20, 0) <= (t.hour, t.minute, t.second) <= (15, 35, 0):
                    is_expiry_squareoff = True

        return NormalizedFill(
            broker_trade_id=trade_id_str,
            broker_order_id=order_id_str,
            broker=_BROKER,
            import_source=_IMPORT_SOURCE,
            symbol_raw=symbol_raw,
            exchange=exchange_raw,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_date=expiry_date,
            strike_price=strike_price,
            trade_date=trade_date,
            fill_timestamp=fill_timestamp,
            session=session,
            side=side,
            quantity=quantity,
            price=price,
            product_type=product_type,
            is_auction=is_auction,
            is_expiry_squareoff=is_expiry_squareoff,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require(row: dict[str, str], field: str, row_idx: int) -> str:
        """Extract a required field from the row dict; raise InvalidFillError if absent/empty."""
        value = row.get(field, "").strip()
        if not value:
            raise InvalidFillError(
                row_idx, field, "", f"Required field {field!r} is missing or empty"
            )
        return value
