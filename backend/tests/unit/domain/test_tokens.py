"""Unit tests for token generation (pure stdlib, no I/O)."""

import re

from tradeforge.domain.auth.tokens import (
    generate_reset_token,
    generate_session_token,
    generate_verification_token,
    sha256_hex,
)

HEX_64 = re.compile(r"^[0-9a-f]{64}$")
HEX_32 = re.compile(r"^[0-9a-f]{32}$")


def test_session_token_is_64_hex_chars() -> None:
    token = generate_session_token()
    assert HEX_64.match(token), f"Expected 64-char hex, got: {token!r}"


def test_verification_token_is_64_hex_chars() -> None:
    token = generate_verification_token()
    assert HEX_64.match(token)


def test_reset_token_is_64_hex_chars() -> None:
    token = generate_reset_token()
    assert HEX_64.match(token)


def test_tokens_are_unique() -> None:
    tokens = {generate_session_token() for _ in range(100)}
    assert len(tokens) == 100


def test_sha256_hex_produces_64_char_lowercase_hex() -> None:
    digest = sha256_hex("hello")
    assert HEX_64.match(digest)


def test_sha256_hex_is_deterministic() -> None:
    assert sha256_hex("same") == sha256_hex("same")


def test_sha256_hex_differs_for_different_inputs() -> None:
    assert sha256_hex("a") != sha256_hex("b")


def test_sha256_hex_of_empty_string() -> None:
    # SHA-256("") is a known value
    assert sha256_hex("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
