"""Unit tests for password domain layer (pure, no I/O)."""

from tradeforge.domain.auth.password import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    validate_password_policy,
)


def test_valid_password_returns_none() -> None:
    assert validate_password_policy("ValidPass123!") is None


def test_too_short_returns_error() -> None:
    short = "a" * (MIN_PASSWORD_LENGTH - 1)
    error = validate_password_policy(short)
    assert error is not None
    assert str(MIN_PASSWORD_LENGTH) in error


def test_exactly_minimum_length_is_valid() -> None:
    password = "a" * MIN_PASSWORD_LENGTH
    assert validate_password_policy(password) is None


def test_too_long_returns_error() -> None:
    long_pass = "a" * (MAX_PASSWORD_LENGTH + 1)
    error = validate_password_policy(long_pass)
    assert error is not None
    assert str(MAX_PASSWORD_LENGTH) in error


def test_exactly_maximum_length_is_valid() -> None:
    password = "a" * MAX_PASSWORD_LENGTH
    assert validate_password_policy(password) is None


def test_empty_password_returns_error() -> None:
    assert validate_password_policy("") is not None


def test_no_complexity_requirement() -> None:
    # ADR-002 has no complexity rules beyond length — only HIBP check (which is async)
    assert validate_password_policy("alllowercasenumbers12") is None
