"""Have I Been Pwned k-anonymity password breach check (SR-AUTH-002).

Only the first 5 hex characters of SHA-1(password) are transmitted to HIBP.
The rest of the check is local.

Semantics (BLOCKER-4):
  - Returns True  → password found in a known breach (caller should reject it).
  - Returns False → password not found (safe to proceed).
  - Raises HibpServiceError → HIBP API unreachable or unexpected response.
    The caller must log HIBP_CHECK_FAILED and fail open (do not block the user).
"""

import hashlib

import httpx


class HibpServiceError(Exception):
    """Raised when the HIBP API cannot be reached or returns an unexpected status."""


async def is_password_pwned(password: str) -> bool:
    """Return True if the password appears in a known breach dataset.

    Raises:
        HibpServiceError: HIBP API unreachable, timed out, or returned non-200.

    Note: callers must NOT raise HibpServiceError back to the user; they should
    log HIBP_CHECK_FAILED and continue (fail open).
    """
    sha1 = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()  # noqa: S324
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true"},
            )
    except Exception as exc:  # noqa: BLE001
        raise HibpServiceError("HIBP API unreachable") from exc

    if response.status_code != 200:
        raise HibpServiceError(f"HIBP API returned HTTP {response.status_code}")

    for line in response.text.splitlines():
        if ":" not in line:
            continue
        hash_suffix, count_str = line.split(":", 1)
        if hash_suffix == suffix and int(count_str.strip()) > 0:
            return True
    return False
