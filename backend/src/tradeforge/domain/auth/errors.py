"""Typed error hierarchy for the auth domain.

These are operational errors (expected failure paths), not programmer errors.
Route handlers catch them and map to appropriate HTTP responses.
"""


class AuthError(Exception):
    """Base class for all auth-layer operational errors."""


class InvalidCredentialsError(AuthError):
    """Wrong email or password. Always returns 401 — never reveals which."""


class AccountLockedError(AuthError):
    """Account is locked due to brute-force threshold or admin action."""


class RateLimitedError(AuthError):
    """Per-IP request rate exceeded (SR-AUTH-003)."""


class InvalidTokenError(AuthError):
    """Verification or reset token is missing, invalid, or expired."""


class EmailNotVerifiedError(AuthError):
    """Login attempted before the email address was verified."""


class PasswordPolicyViolationError(AuthError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class RedisUnavailableError(AuthError):
    """Redis is unreachable; fail closed per SR-AUTH-021 Rule D."""
