"""Email sender abstraction.

Local dev → SmtpEmailSender (Mailpit on port 1025).
Production → ResendEmailSender (Phase 2, not yet implemented).

EmailSender is a structural Protocol so tests can inject any callable duck-type.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

import aiosmtplib


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, html_body: str) -> None: ...


class SmtpEmailSender:
    def __init__(self, host: str, port: int, from_address: str) -> None:
        self._host = host
        self._port = port
        self._from = from_address

    async def send(self, to: str, subject: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))
        await aiosmtplib.send(
            msg,
            hostname=self._host,
            port=self._port,
        )


def get_email_sender() -> EmailSender:
    """Factory: return the correct EmailSender for the current transport setting."""
    from tradeforge.settings import get_settings

    settings = get_settings()
    transport = settings.email_transport.lower()
    from_addr = settings.from_address or "noreply@tradeforge.local"

    if transport == "smtp":
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_address=from_addr,
        )
    # Phase 2: return ResendEmailSender(...)
    raise ValueError(f"Unsupported EMAIL_TRANSPORT: {transport!r}")
