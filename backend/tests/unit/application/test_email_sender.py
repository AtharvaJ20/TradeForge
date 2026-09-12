"""Unit tests for email sender implementations.

Covers:
  - ResendEmailSender sends correct payload to Resend API
  - ResendEmailSender wraps non-2xx Resend API response as EmailDeliveryError
  - ResendEmailSender wraps network failure as EmailDeliveryError
  - get_email_sender() returns ResendEmailSender when EMAIL_TRANSPORT=resend
  - get_email_sender() raises ValueError when EMAIL_TRANSPORT=resend but RESEND_API_KEY is empty
  - get_email_sender() raises ValueError for unknown transport
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tradeforge.application.auth.email import (
    ConsoleEmailSender,
    ResendEmailSender,
    get_email_sender,
)
from tradeforge.domain.auth.errors import EmailDeliveryError

# ---------------------------------------------------------------------------
# ResendEmailSender — happy path
# ---------------------------------------------------------------------------


async def test_resend_sender_posts_correct_payload() -> None:
    sender = ResendEmailSender(api_key="re_test_key", from_address="onboarding@resend.dev")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        await sender.send("user@example.com", "Verify your email", "<p>Click here</p>")

        mock_client.post.assert_called_once_with(
            "https://api.resend.com/emails",
            headers={"Authorization": "Bearer re_test_key"},
            json={
                "from": "onboarding@resend.dev",
                "to": ["user@example.com"],
                "subject": "Verify your email",
                "html": "<p>Click here</p>",
            },
            timeout=10.0,
        )
        mock_response.raise_for_status.assert_called_once()


# ---------------------------------------------------------------------------
# ResendEmailSender — error paths
# ---------------------------------------------------------------------------


async def test_resend_sender_wraps_api_error_as_email_delivery_error() -> None:
    sender = ResendEmailSender(api_key="re_test_key", from_address="onboarding@resend.dev")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(),
        )
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        with pytest.raises(EmailDeliveryError):
            await sender.send("user@example.com", "Subject", "<p>Body</p>")


async def test_resend_sender_wraps_network_failure_as_email_delivery_error() -> None:
    sender = ResendEmailSender(api_key="re_test_key", from_address="onboarding@resend.dev")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_cls.return_value = mock_client

        with pytest.raises(EmailDeliveryError):
            await sender.send("user@example.com", "Subject", "<p>Body</p>")


# ---------------------------------------------------------------------------
# ConsoleEmailSender — DEF-DASH-005 regression
# ---------------------------------------------------------------------------


async def test_console_sender_completes_without_error() -> None:
    sender = ConsoleEmailSender()
    # Must not raise — no external call, just logs to stdout
    await sender.send("user@example.com", "Verify your email", "<p>Token: ABC123</p>")


# ---------------------------------------------------------------------------
# get_email_sender() factory — console transport (DEF-DASH-005)
# ---------------------------------------------------------------------------


def test_get_email_sender_returns_console_sender_when_configured() -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "REDIS_URL": "redis://localhost",
        "EMAIL_TRANSPORT": "console",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": "test-secret",
    }
    with patch.dict("os.environ", env, clear=True):
        sender = get_email_sender()
        assert isinstance(sender, ConsoleEmailSender)


# ---------------------------------------------------------------------------
# get_email_sender() factory — resend transport
# ---------------------------------------------------------------------------


def test_get_email_sender_returns_resend_sender_when_configured() -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "REDIS_URL": "redis://localhost",
        "EMAIL_TRANSPORT": "resend",
        "RESEND_API_KEY": "re_live_abc123",
        "FROM_ADDRESS": "onboarding@resend.dev",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": "test-secret",
    }
    with patch.dict("os.environ", env, clear=True):
        sender = get_email_sender()
        assert isinstance(sender, ResendEmailSender)


def test_get_email_sender_raises_when_resend_api_key_missing() -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "REDIS_URL": "redis://localhost",
        "EMAIL_TRANSPORT": "resend",
        "RESEND_API_KEY": "",
        "FROM_ADDRESS": "onboarding@resend.dev",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": "test-secret",
    }
    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(ValueError, match="RESEND_API_KEY"):
            get_email_sender()


def test_get_email_sender_raises_for_unknown_transport() -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "REDIS_URL": "redis://localhost",
        "EMAIL_TRANSPORT": "sendgrid",
        "RESEND_API_KEY": "",
        "FROM_ADDRESS": "noreply@example.com",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": "test-secret",
    }
    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(ValueError, match="Unsupported EMAIL_TRANSPORT"):
            get_email_sender()
