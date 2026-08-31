"""Regression tests for JournalEntryRequest and PresignRequest Pydantic validation.

Covers D-002 (price > 0) and D-003 (enum validation for emotions, mistakes,
capture_moment). No database, no HTTP — pure model-level unit tests.
"""

from __future__ import annotations

import pytest
from decimal import Decimal
from pydantic import ValidationError

from tradeforge.api.v1.journal import JournalEntryRequest, PresignRequest


# ---------------------------------------------------------------------------
# D-002 — planned_entry / planned_stop / planned_target must be > 0
# ---------------------------------------------------------------------------


class TestPriceFieldValidation:
    """API spec: planned_entry/stop/target ≤ 0 → 422. G1 Rule 2.2."""

    @pytest.mark.parametrize("field", ["planned_entry", "planned_stop", "planned_target"])
    def test_zero_price_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            JournalEntryRequest(**{field: Decimal("0")})
        errors = exc_info.value.errors()
        assert any(e["loc"][-1] == field for e in errors)

    @pytest.mark.parametrize("field", ["planned_entry", "planned_stop", "planned_target"])
    def test_negative_price_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            JournalEntryRequest(**{field: Decimal("-1")})
        errors = exc_info.value.errors()
        assert any(e["loc"][-1] == field for e in errors)

    @pytest.mark.parametrize("field", ["planned_entry", "planned_stop", "planned_target"])
    def test_positive_price_accepted(self, field: str) -> None:
        req = JournalEntryRequest(**{field: Decimal("500.25")})
        assert getattr(req, field) == Decimal("500.25")

    @pytest.mark.parametrize("field", ["planned_entry", "planned_stop", "planned_target"])
    def test_none_accepted(self, field: str) -> None:
        req = JournalEntryRequest(**{field: None})
        assert getattr(req, field) is None

    def test_empty_body_valid(self) -> None:
        """A completely empty body is valid — all fields are optional."""
        req = JournalEntryRequest()
        assert req.planned_stop is None
        assert req.discipline_score is None


# ---------------------------------------------------------------------------
# D-003 — emotion_* must be a valid EmotionType
# ---------------------------------------------------------------------------


class TestEmotionValidation:
    """API spec: unknown emotion_* value → 422. G1 Rule 2.7."""

    @pytest.mark.parametrize("field", ["emotion_before", "emotion_during", "emotion_after"])
    def test_invalid_emotion_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            JournalEntryRequest(**{field: "EUPHORIC_PANIC"})
        errors = exc_info.value.errors()
        assert any(e["loc"][-1] == field for e in errors)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("emotion_before", "CALM"),
            ("emotion_during", "CONFIDENT"),
            ("emotion_after", "NEUTRAL"),
            ("emotion_before", "ANXIOUS"),
            ("emotion_during", "EUPHORIC"),
        ],
    )
    def test_valid_emotion_accepted(self, field: str, value: str) -> None:
        req = JournalEntryRequest(**{field: value})
        assert getattr(req, field) == value

    @pytest.mark.parametrize("field", ["emotion_before", "emotion_during", "emotion_after"])
    def test_none_accepted(self, field: str) -> None:
        req = JournalEntryRequest(**{field: None})
        assert getattr(req, field) is None

    @pytest.mark.parametrize("field", ["emotion_before", "emotion_during", "emotion_after"])
    def test_lowercase_emotion_rejected(self, field: str) -> None:
        """Enum values are case-sensitive — 'calm' is not 'CALM'."""
        with pytest.raises(ValidationError):
            JournalEntryRequest(**{field: "calm"})


# ---------------------------------------------------------------------------
# D-003 — mistakes must contain only valid MistakeType values
# ---------------------------------------------------------------------------


class TestMistakesValidation:
    """API spec: unknown mistakes element → 422. G1 Rule 2.6."""

    def test_invalid_mistake_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            JournalEntryRequest(mistakes=["FOMO_ENTRY", "INVENTED_MISTAKE"])
        errors = exc_info.value.errors()
        assert any(e["loc"][-1] == "mistakes" for e in errors)

    def test_all_invalid_mistakes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JournalEntryRequest(mistakes=["NOT_A_MISTAKE"])

    def test_valid_mistakes_accepted(self) -> None:
        req = JournalEntryRequest(
            mistakes=["FOMO_ENTRY", "HELD_THROUGH_STOP", "REVENGE_TRADE"]
        )
        assert req.mistakes == ["FOMO_ENTRY", "HELD_THROUGH_STOP", "REVENGE_TRADE"]

    def test_empty_mistakes_list_accepted(self) -> None:
        req = JournalEntryRequest(mistakes=[])
        assert req.mistakes == []

    def test_none_mistakes_accepted(self) -> None:
        req = JournalEntryRequest(mistakes=None)
        assert req.mistakes is None

    def test_all_13_mistake_types_accepted(self) -> None:
        all_mistakes = [
            "FOMO_ENTRY", "FOMO_EXIT", "OVERSIZED_POSITION", "NO_STOP_DEFINED",
            "MOVED_STOP_WIDER", "CUT_WINNER_EARLY", "HELD_THROUGH_STOP",
            "REVENGE_TRADE", "AVERAGING_DOWN", "ENTRY_TOO_EARLY",
            "ENTRY_TOO_LATE", "IGNORED_SIGNAL", "DISTRACTED",
        ]
        req = JournalEntryRequest(mistakes=all_mistakes)
        assert len(req.mistakes) == 13  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# D-003 — capture_moment must be a valid CaptureMoment in PresignRequest
# ---------------------------------------------------------------------------


class TestCaptureMomentValidation:
    """API spec: unknown capture_moment → 422. G1 Rule 5.5."""

    def test_invalid_capture_moment_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PresignRequest(
                filename="chart.png",
                content_type="image/png",
                byte_size=1024,
                capture_moment="BEFORE_SLEEP",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][-1] == "capture_moment" for e in errors)

    @pytest.mark.parametrize(
        "moment", ["AT_ENTRY", "DURING_TRADE", "AT_EXIT", "POST_REVIEW"]
    )
    def test_valid_capture_moments_accepted(self, moment: str) -> None:
        req = PresignRequest(
            filename="chart.png",
            content_type="image/png",
            byte_size=1024,
            capture_moment=moment,
        )
        assert req.capture_moment == moment

    def test_lowercase_capture_moment_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PresignRequest(
                filename="chart.png",
                content_type="image/png",
                byte_size=1024,
                capture_moment="at_entry",
            )
