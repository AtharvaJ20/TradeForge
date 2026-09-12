"""Unit tests for email sender implementations.

Covers:
  - SmtpEmailSender without credentials (Mailpit) — no STARTTLS, no auth
  - SmtpEmailSender with credentials (Gmail) — STARTTLS enabled, auth passed
  - SmtpEmailSender wraps SMTP failure as EmailDeliveryError
  - ResendEmailSender sends correct payload to Resend API
  - ResendEmailSender wraps non-2xx Resend API response as EmailDeliveryError
  - ResendEmailSender wraps network failure as EmailDeliveryError
  - get_email_sender() returns ResendEmailSender when EMAIL_TRANSPORT=resend
  - get_email_sender() raises ValueError when EMAIL_TRANSPORT=resend but RESEND_API_KEY is empty
  - get_email_sender() raises ValueError for unknown transport
  - get_email_sender() returns SmtpEmailSender when EMAIL_TRANSPORT=smtp
  - get_email_sender() raises ValueError when SMTP_USER set without SMTP_PASSWORD
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tradeforge.application.auth.email import (
    ConsoleEmailSender,
    ResendEmailSender,
    SmtpEmailSender,
    get_email_sender,
)
from tradeforge.domain.auth.errors import EmailDeliveryError

# ---------------------------------------------------------------------------
# SmtpEmailSender — unauthenticated (Mailpit local dev)
# ---------------------------------------------------------------------------


async def test_smtp_sender_no_auth_sends_without_starttls() -> None:
    sender = SmtpEmailSender(host="localhost", port=1025, from_address="test@local")

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await sender.send("user@example.com", "Hello", "<p>Hi</p>")

        mock_send.assert_awaited_once()
        _, kwargs = mock_send.call_args
        assert kwargs["hostname"] == "localhost"
        assert kwargs["port"] == 1025
        assert kwargs["start_tls"] is False
        assert kwargs["username"] is None
        assert kwargs["password"] is None


# ---------------------------------------------------------------------------
# SmtpEmailSender — authenticated (Gmail SMTP)
# ---------------------------------------------------------------------------


async def test_smtp_sender_with_auth_enables_starttls_and_passes_credentials() -> None:
    sender = SmtpEmailSender(
        host="smtp.gmail.com",
        port=587,
        from_address="jadhavatharva20@gmail.com",
        username="jadhavatharva20@gmail.com",
        password="app-password-here",
    )

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await sender.send("recipient@example.com", "Reset your password", "<p>Link</p>")

        mock_send.assert_awaited_once()
        _, kwargs = mock_send.call_args
        assert kwargs["hostname"] == "smtp.gmail.com"
        assert kwargs["port"] == 587
        assert kwargs["start_tls"] is True
        assert kwargs["username"] == "jadhavatharva20@gmail.com"
        assert kwargs["password"] == "app-password-here"


async def test_smtp_sender_strips_spaces_from_app_password() -> None:
    """Regression: Gmail App Passwords are displayed with spaces (e.g. 'abcd efgh ijkl mnop').
    The spaces must be stripped before passing to aiosmtplib — otherwise SMTP auth fails."""
    sender = SmtpEmailSender(
        host="smtp.gmail.com",
        port=587,
        from_address="sender@gmail.com",
        username="sender@gmail.com",
        password="abcd efgh ijkl mnop",
    )

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await sender.send("to@example.com", "Subject", "<p>Body</p>")

        _, kwargs = mock_send.call_args
        assert kwargs["password"] == "abcdefghijklmnop"


async def test_smtp_sender_attaches_plain_text_and_html_parts() -> None:
    """SMTP messages must include a text/plain alternative alongside HTML.
    HTML-only emails are flagged by spam filters and silently dropped by Gmail."""
    sender = SmtpEmailSender(host="localhost", port=1025, from_address="test@local")

    captured: list = []

    async def capture_send(msg, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(msg)

    with patch("aiosmtplib.send", new_callable=AsyncMock, side_effect=capture_send):
        await sender.send("user@example.com", "Subject", "<p>Hello <strong>world</strong></p>")

    assert len(captured) == 1
    msg = captured[0]
    content_types = [part.get_content_type() for part in msg.walk()]
    assert "text/plain" in content_types, "Missing text/plain MIME part"
    assert "text/html" in content_types, "Missing text/html MIME part"

    plain_part = next(p for p in msg.walk() if p.get_content_type() == "text/plain")
    plain_text = plain_part.get_payload(decode=True).decode()
    assert "Hello" in plain_text
    assert "world" in plain_text
    assert "<p>" not in plain_text, "Plain text part must not contain HTML tags"


async def test_smtp_sender_wraps_failure_as_email_delivery_error() -> None:
    sender = SmtpEmailSender(
        host="smtp.gmail.com",
        port=587,
        from_address="from@gmail.com",
        username="from@gmail.com",
        password="bad-password",
    )

    with patch("aiosmtplib.send", new_callable=AsyncMock, side_effect=Exception("auth failed")):
        with pytest.raises(EmailDeliveryError, match="SMTP delivery failed"):
            await sender.send("to@example.com", "Subject", "<p>Body</p>")


# ---------------------------------------------------------------------------
# get_email_sender() factory — smtp transport
# ---------------------------------------------------------------------------


def test_get_email_sender_returns_smtp_sender_when_configured() -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "REDIS_URL": "redis://localhost",
        "EMAIL_TRANSPORT": "smtp",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "jadhavatharva20@gmail.com",
        "SMTP_PASSWORD": "my-app-password",
        "FROM_ADDRESS": "jadhavatharva20@gmail.com",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": "test-secret",
    }
    with patch.dict("os.environ", env, clear=True):
        sender = get_email_sender()
        assert isinstance(sender, SmtpEmailSender)


def test_get_email_sender_raises_when_smtp_user_set_without_password() -> None:
    env = {
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
        "REDIS_URL": "redis://localhost",
        "EMAIL_TRANSPORT": "smtp",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "jadhavatharva20@gmail.com",
        "SMTP_PASSWORD": "",
        "FROM_ADDRESS": "jadhavatharva20@gmail.com",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": "test-secret",
    }
    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(ValueError, match="SMTP_PASSWORD"):
            get_email_sender()


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
