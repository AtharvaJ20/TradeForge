"""Password policy validation — pure functions, no I/O (SR-AUTH-002)."""

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def validate_password_policy(password: str) -> str | None:
    """Return an error message if the password violates policy, else None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must not exceed {MAX_PASSWORD_LENGTH} characters."
    return None
