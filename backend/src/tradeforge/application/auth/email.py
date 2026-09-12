"""Email sender abstraction.

Local dev → SmtpEmailSender (Mailpit on port 1025).
Staging (no SMTP) → ConsoleEmailSender (prints to stdout; visible in Railway logs).
Production → ResendEmailSender (Resend API via httpx).

EmailSender is a structural Protocol so tests can inject any callable duck-type.
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

import aiosmtplib
import httpx

_log = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, html_body: str) -> None: ...


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        from_address: str,
        username: str = "",
        password: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._from = from_address
        self._username = username
        self._password = password.replace(" ", "")

    async def send(self, to: str, subject: str, html_body: str) -> None:
        from tradeforge.domain.auth.errors import EmailDeliveryError

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        use_starttls = bool(self._username)
        try:
            await aiosmtplib.send(
                msg,
                hostname=self._host,
                port=self._port,
                start_tls=use_starttls,
                username=self._username or None,
                password=self._password or None,
                timeout=30,
            )
        except Exception as exc:
            raise EmailDeliveryError(f"SMTP delivery failed: {exc}") from exc


class ConsoleEmailSender:
    """Logs email to stdout — use on staging where no SMTP/API is configured."""

    async def send(self, to: str, subject: str, html_body: str) -> None:
        _log.info(
            "[ConsoleEmailSender] To: %s | Subject: %s | Body: %s",
            to,
            subject,
            html_body,
        )


class ResendEmailSender:
    """Send transactional email via the Resend API (https://resend.com)."""

    def __init__(self, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from = from_address

    async def send(self, to: str, subject: str, html_body: str) -> None:
        from tradeforge.domain.auth.errors import EmailDeliveryError

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"from": self._from, "to": [to], "subject": subject, "html": html_body},
                    timeout=10.0,
                )
                response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise EmailDeliveryError(f"Resend API error: {exc}") from exc


def get_email_sender() -> EmailSender:
    """Factory: return the correct EmailSender for the current transport setting.

    Supported values for EMAIL_TRANSPORT:
      smtp    — local dev (Mailpit on port 1025)
      console — staging (logs to stdout; no external service needed)
      resend  — production (Resend API)
    """
    from tradeforge.settings import get_settings

    settings = get_settings()
    transport = settings.email_transport.lower()
    from_addr = settings.from_address or "noreply@tradeforge.local"

    if transport == "smtp":
        if settings.smtp_user and not settings.smtp_password:
            raise ValueError("SMTP_PASSWORD must be set when SMTP_USER is provided")
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_address=from_addr,
            username=settings.smtp_user,
            password=settings.smtp_password,
        )
    if transport == "console":
        return ConsoleEmailSender()
    if transport == "resend":
        if not settings.resend_api_key:
            raise ValueError("RESEND_API_KEY must be set when EMAIL_TRANSPORT=resend")
        return ResendEmailSender(
            api_key=settings.resend_api_key,
            from_address=from_addr,
        )
    raise ValueError(f"Unsupported EMAIL_TRANSPORT: {transport!r}")
