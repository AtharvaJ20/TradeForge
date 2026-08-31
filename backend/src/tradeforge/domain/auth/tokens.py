"""Token generation — pure stdlib, no I/O.

Tokens are generated as raw hex strings and stored as SHA-256 hashes in the
database (SR-AUTH-006). The raw token is sent to the user; only the hash
lives in persistent storage.
"""

import hashlib
import secrets


def generate_session_token() -> str:
    """256-bit CSPRNG opaque token for Redis-backed sessions (SR-AUTH-006)."""
    return secrets.token_hex(32)


def generate_verification_token() -> str:
    """256-bit CSPRNG email verification token; caller stores sha256_hex(token) in DB."""
    return secrets.token_hex(32)


def generate_reset_token() -> str:
    """256-bit CSPRNG password reset token; caller stores sha256_hex(token) in DB."""
    return secrets.token_hex(32)


def sha256_hex(value: str) -> str:
    """SHA-256 hash of a UTF-8 string returned as lowercase hex."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_hex_bytes(value: str) -> str:
    """Alias of sha256_hex — named to clarify use for email-based keys."""
    return sha256_hex(value)
