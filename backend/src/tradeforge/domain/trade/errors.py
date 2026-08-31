"""Typed exceptions raised by the trade reconstruction engine.

These are domain errors — they carry no framework dependency and may be raised
from any layer. See TRADE-RECONSTRUCTION-SPEC.md §12 for the full error taxonomy.
"""

from __future__ import annotations

import uuid


class ReconstructionError(Exception):
    """Base class for all trade reconstruction errors."""


class PositionCrossingZeroError(ReconstructionError):
    """E1 — a single fill would cause running_position to cross zero.

    This means the fill simultaneously closes an existing trade and opens a new
    one in the opposite direction, which cannot be represented by a single
    execution_fill row. Reconstruction is halted for the affected processing unit.

    Resolution: split into two MANUAL fills and add the original to fill_exclusions.
    """

    def __init__(self, fill_id: uuid.UUID) -> None:
        self.fill_id = fill_id
        super().__init__(
            f"Fill {fill_id} would cause running_position to cross zero. "
            "Reconstruction halted. Split into a closing fill and an opening fill, "
            "then record the original in fill_exclusions."
        )


class ReconstructionDataError(ReconstructionError):
    """E2 — data inconsistency: wrong product_type_family, unrecognised enum value, etc."""


class ReconstructionAmbiguityError(ReconstructionError):
    """E5 — two fills share identical fill_timestamp with no deterministic tiebreaker.

    Both fills have NULL fill_id and identical created_at, so the engine cannot
    assign a deterministic order. Operator must set fill_id or adjust fill_timestamp.
    """

    def __init__(self, fill_a_id: uuid.UUID, fill_b_id: uuid.UUID) -> None:
        self.fill_a_id = fill_a_id
        self.fill_b_id = fill_b_id
        super().__init__(
            f"Ambiguous fill ordering between fills {fill_a_id} and {fill_b_id}: "
            "identical fill_timestamp, both fill_id NULL, identical created_at. "
            "Provide a fill_id or adjust fill_timestamp by at least one second."
        )


class ReconstructionConsistencyError(ReconstructionError):
    """E4 — post-close consistency assertion failed.

    Covers: no open tax lot found for a CNC exit, tax lot quantity_remaining ≠ 0
    after trade close, or other invariant violations.
    """
