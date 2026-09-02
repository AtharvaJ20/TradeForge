"""Typed domain errors for the broker import pipeline.

No framework imports.  All errors are raised from domain or adapter code and
caught at the application (ImportService) boundary.
"""

from __future__ import annotations


class ImportDomainError(Exception):
    """Base class for all import-domain errors."""


class AccountNotFoundError(ImportDomainError):
    """The requested trading account does not exist or is not owned by the caller."""

    def __init__(self, account_id: object) -> None:
        super().__init__(f"Trading account not found: {account_id}")
        self.account_id = account_id


class AccountInactiveError(ImportDomainError):
    """Import rejected because the target account has status = INACTIVE."""

    def __init__(self, account_id: object) -> None:
        super().__init__(f"Trading account is inactive: {account_id}")
        self.account_id = account_id


class DuplicateImportError(ImportDomainError):
    """The same file (same SHA-256 hash) has already been imported into this account."""

    def __init__(self, file_hash: str, account_id: object) -> None:
        super().__init__(
            f"File with hash {file_hash!r} was already imported into account {account_id}"
        )
        self.file_hash = file_hash
        self.account_id = account_id


class InvalidFillError(ImportDomainError):
    """A single CSV row failed validation.

    The import continues with the remaining rows.  Errors are collected in the
    AdapterParseResult and reported in the ImportRecord.
    """

    def __init__(
        self,
        row_index: int,
        field_name: str,
        raw_value: str,
        message: str,
    ) -> None:
        super().__init__(f"Row {row_index}: field {field_name!r} = {raw_value!r} — {message}")
        self.row_index = row_index
        self.field_name = field_name
        self.raw_value = raw_value
        self.message = message


class MissingProductTypeError(ImportDomainError):
    """The tradebook lacks the 'product' column and no product_type_hint was provided.

    Raised before any rows are parsed.  The entire import is halted.
    """

    DEFAULT_MESSAGE = (
        "This tradebook does not contain a 'product' column. "
        "Provide product_type_hint='MIS', 'CNC', or 'NRML' to classify fills. "
        "If the file contains mixed product types (e.g. both MIS and NRML F&O), "
        "perform separate imports per product type."
    )

    def __init__(self, message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)


class AdapterNotFoundError(ImportDomainError):
    """No registered adapter can handle the uploaded file."""

    def __init__(self, broker: str) -> None:
        super().__init__(f"No adapter registered for broker: {broker!r}")
        self.broker = broker


class UnrecognizedFileError(ImportDomainError):
    """The file format was not recognized by any adapter's detect() method."""

    def __init__(self) -> None:
        super().__init__("File format not recognized. Ensure this is a valid broker tradebook CSV.")


class EmptyFileError(ImportDomainError):
    """The CSV file has a header but zero data rows."""

    def __init__(self) -> None:
        super().__init__("The uploaded file contains no data rows.")


class InstrumentNotFoundError(ImportDomainError):
    """No instrument record matched the fill's symbol/exchange/segment/type."""

    def __init__(self, symbol_raw: str, exchange_segment: str, instrument_type: str) -> None:
        super().__init__(
            f"Instrument not found: {symbol_raw!r} ({exchange_segment}, {instrument_type})"
        )
        self.symbol_raw = symbol_raw
        self.exchange_segment = exchange_segment
        self.instrument_type = instrument_type
