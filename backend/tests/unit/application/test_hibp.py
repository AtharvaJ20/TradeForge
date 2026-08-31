"""Unit tests for HIBP k-anonymity check — correct error semantics (BLOCKER-4).

Covers:
  - HibpServiceError raised on network failure (no HTTP response)
  - HibpServiceError raised on non-200 HTTP response
  - Returns True when the SHA-1 suffix appears in the response with count > 0
  - Returns False when the SHA-1 suffix is absent from the response
  - Returns False when the suffix appears with count == 0 (padded entry)
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradeforge.application.auth.hibp import HibpServiceError, is_password_pwned


def _sha1_upper(password: str) -> str:
    return hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()


def _hibp_response_body(password: str, count: int) -> str:
    """Build a minimal HIBP response body that contains the given password's suffix."""
    sha1 = _sha1_upper(password)
    suffix = sha1[5:]
    return f"{suffix}:{count}\nABCDE123456789:1\n"


# ------------------------------------------------------------------
# HibpServiceError on API/network failures
# ------------------------------------------------------------------


async def test_network_error_raises_hibp_service_error() -> None:
    """A network exception (e.g. timeout, DNS failure) must raise HibpServiceError."""
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_cls.return_value = mock_client

        with pytest.raises(HibpServiceError):
            await is_password_pwned("SomePassword123!")


async def test_non_200_response_raises_hibp_service_error() -> None:
    """A non-200 HTTP status from HIBP must raise HibpServiceError, not return False."""
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = ""

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        with pytest.raises(HibpServiceError):
            await is_password_pwned("SomePassword123!")


async def test_429_response_raises_hibp_service_error() -> None:
    """Rate-limited HIBP response (429) must raise HibpServiceError."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = ""

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        with pytest.raises(HibpServiceError):
            await is_password_pwned("SomePassword123!")


# ------------------------------------------------------------------
# Positive breach match
# ------------------------------------------------------------------


async def test_returns_true_when_password_is_breached() -> None:
    """A 200 response containing the password suffix with count > 0 returns True."""
    password = "hunter2"
    body = _hibp_response_body(password, count=9999)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = body

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        assert await is_password_pwned(password) is True


# ------------------------------------------------------------------
# Negative results (password is safe)
# ------------------------------------------------------------------


async def test_returns_false_when_suffix_absent() -> None:
    """A 200 response that does not contain the password suffix returns False."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "11111111111111111111111111111111111:5\n"

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        assert await is_password_pwned("NotInThisList!99") is False


async def test_returns_false_when_count_is_zero() -> None:
    """A suffix present with count=0 (HIBP padding) must not be treated as a breach."""
    password = "PaddedEntry!99"
    body = _hibp_response_body(password, count=0)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = body

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        assert await is_password_pwned(password) is False
