"""BrokerAdapterPort — structural Protocol for broker CSV adapters.

Any class that implements detect() and parse() with the correct signatures
satisfies this Protocol without explicit inheritance (structural subtyping).

The adapter is responsible for:
  - Detecting whether the uploaded file matches its broker's format (detect)
  - Parsing raw bytes into a list of NormalizedFill value objects (parse)

The adapter is NOT responsible for:
  - Instrument resolution (instrument_id lookup)
  - Deduplication (DB query)
  - Writing to execution_fills
  - Trade reconstruction
  - P&L calculation
  - account_id / user_id assignment

See NORMALIZED-FILL-CONTRACT.md §7 for the complete boundary definition.
"""

from __future__ import annotations

from typing import Protocol

from tradeforge.domain.import_domain.types import AdapterParseResult


class BrokerAdapterPort(Protocol):
    """Structural Protocol — implement detect() and parse() to satisfy it."""

    def detect(self, file_content: bytes) -> bool:
        """Return True if this adapter recognises the file format.

        Must not raise.  Must not perform heavy parsing — header inspection only.
        """
        ...

    def parse(
        self,
        file_content: bytes,
        product_type_hint: str | None = None,
    ) -> AdapterParseResult:
        """Parse raw broker file bytes into normalised fills.

        Args:
            file_content: Raw bytes of the uploaded file.
            product_type_hint: Caller-declared product type ('MIS', 'CNC', 'NRML').
                Required when the file lacks a 'product' column and contains rows
                that cannot be classified structurally (see §3.4).

        Returns:
            AdapterParseResult with a fills list and a (possibly empty) errors list.
            Valid rows are in fills; per-row failures are in errors.

        Raises:
            EmptyFileError: CSV has a header but zero data rows.
            MissingProductTypeError: product column absent, hint not provided,
                and at least one row requires the hint for classification.
            UnrecognizedFileError: detect() would return False for this content.
        """
        ...
