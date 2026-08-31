"""Decimal hygiene assertions from DECIMAL-USAGE-STANDARD.md Rule 10.

These tests verify the constants themselves and the rounding behaviour they
encode. They do not test P&L logic — that is Sahadeva's domain once Kubera's
charge engine is implemented.

Per ADR-001: domain layer tests must run with no database, no HTTP server,
and no network access. This file proves that contract — it imports only from
the domain layer and Python stdlib.
"""

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from tradeforge.domain.decimal_config import (
    CHARGE_STORED,
    FOUR_PLACES,
    MONETARY,
    PERCENTAGE,
    PRICE,
    QUANTITY,
    R_MULTIPLE,
    SIX_PLACES,
    TWO_PLACES,
    ZERO,
)


def test_decimal_addition_is_exact() -> None:
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")


def test_round_half_up_on_point_five() -> None:
    result = Decimal("2.5").quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    assert result == Decimal("3")


def test_round_half_even_differs_on_point_five() -> None:
    result = Decimal("2.5").quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    assert result == Decimal("2")


def test_monetary_rounds_to_two_places() -> None:
    value = Decimal("100.12345")
    assert value.quantize(*MONETARY) == Decimal("100.12")


def test_monetary_uses_round_half_up() -> None:
    assert Decimal("0.005").quantize(*MONETARY) == Decimal("0.01")
    assert Decimal("0.004").quantize(*MONETARY) == Decimal("0.00")


def test_price_rounds_to_four_places() -> None:
    value = Decimal("251.42505")
    assert value.quantize(*PRICE) == Decimal("251.4251")


def test_quantity_rounds_down_never_up() -> None:
    # ROUND_DOWN toward zero — a quantity can never be rounded up
    assert Decimal("10.00009").quantize(*QUANTITY) == Decimal("10.0000")
    assert Decimal("10.99999").quantize(*QUANTITY) == Decimal("10.9999")


def test_zero_constant_is_decimal() -> None:
    assert isinstance(ZERO, Decimal)
    assert ZERO == Decimal("0")


def test_all_constants_are_decimal_instances() -> None:
    for name, constant in [
        ("TWO_PLACES", TWO_PLACES),
        ("FOUR_PLACES", FOUR_PLACES),
    ]:
        assert isinstance(constant, Decimal), f"{name} must be a Decimal"


def test_bundle_places() -> None:
    places = {
        "MONETARY": (MONETARY, TWO_PLACES),
        "PRICE": (PRICE, FOUR_PLACES),
        "CHARGE_STORED": (CHARGE_STORED, FOUR_PLACES),
        "R_MULTIPLE": (R_MULTIPLE, SIX_PLACES),
        "PERCENTAGE": (PERCENTAGE, FOUR_PLACES),
        "QUANTITY": (QUANTITY, FOUR_PLACES),
    }
    for name, (bundle, expected_places) in places.items():
        assert bundle[0] == expected_places, f"{name}[0] must be {expected_places}"
