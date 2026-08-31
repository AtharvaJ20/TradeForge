"""AuthService — orchestrates all authentication use cases.

Security requirements implemented here:
  SR-AUTH-001  Argon2id, memory=64MB, iterations=3, parallelism=2
  SR-AUTH-002  Password policy + HIBP check on registration (fail open)
  SR-AUTH-003  Brute-force: 5 failures/15min per account, 50/60s per IP
  SR-AUTH-004  Enumeration prevention: register + reset-request always return
  SR-AUTH-006  256-bit opaque session tokens, 30-day TTL
  SR-AUTH-007  New session token on each login (session-fixation prevention)
  SR-AUTH-008  user_id sourced from session context, never request body
  SR-AUTH-010  Password change triggers full session revocation + forced_reauth
  SR-AUTH-018  All required audit events are logged

NEVER include passwords, tokens, or session data in log output or API responses.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from tradeforge.application.auth.email import EmailSender
from tradeforge.application.auth.hibp import HibpServiceError, is_password_pwned
from tradeforge.domain.auth.errors import (
    AccountLockedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordPolicyViolationError,
    RateLimitedError,
    RedisUnavailableError,
)
from tradeforge.domain.auth.events import AuditEventType
from tradeforge.domain.auth.password import validate_password_policy
from tradeforge.domain.auth.tokens import (
    generate_reset_token,
    generate_session_token,
    generate_verification_token,
    sha256_hex,
)
from tradeforge.infrastructure.repositories.auth_repo import (
    AuditLogRepository,
    PendingResetRepository,
    PendingVerificationRepository,
)
from tradeforge.infrastructure.repositories.session_repo import (
    IP_ATTEMPT_THRESHOLD,
    LOGIN_FAILURE_THRESHOLD,
    SessionRepository,
)

# Re-export for callers that need the threshold value (e.g. test assertions).
__all__ = ["AuthService"]
from tradeforge.infrastructure.repositories.user_repo import UserRepository

# Argon2id parameters — SR-AUTH-001
_ph = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=2)

# Module-level dummy hash for timing-safe "user not found" path
_DUMMY_HASH: str = _ph.hash("_dummy_for_timing_protection_")

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)


def _ua_hash(user_agent: str | None) -> str:
    if not user_agent:
        return ""
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:16]


def _email_hash(email: str) -> str:
    """One-way hash of email used as Redis key; avoids storing PII in key names."""
    return hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:32]


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditLogRepository,
        verification_repo: PendingVerificationRepository,
        reset_repo: PendingResetRepository,
        session_repo: SessionRepository,
        email_sender: EmailSender,
    ) -> None:
        self._users = user_repo
        self._audit = audit_repo
        self._verifications = verification_repo
        self._resets = reset_repo
        self._sessions = session_repo
        self._email = email_sender

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, email: str, password: str, ip: str) -> None:
        """Always returns None — enumeration prevention (SR-AUTH-004).

        If the email is already registered, send a "someone tried to register"
        notification so the real owner knows. Never reveal existence to the caller.
        """
        # Per-IP rate limit (BLOCKER-3): rejects credential-stuffing at the registration door.
        ip_count = await self._sessions.increment_auth_attempts_ip(ip)
        if ip_count > IP_ATTEMPT_THRESHOLD:
            raise RateLimitedError("Too many registration attempts from this IP.")

        await self._audit.log(
            AuditEventType.REGISTRATION_ATTEMPTED,
            ip_address=ip,
            event_data={"email_hash": _email_hash(email)},
        )

        policy_error = validate_password_policy(password)
        if policy_error is not None:
            raise PasswordPolicyViolationError(policy_error)

        # HIBP check (SR-AUTH-002).
        # HibpServiceError → log HIBP_CHECK_FAILED and fail open (do not block registration).
        # Positive breach match → reject without logging HIBP_CHECK_FAILED (BLOCKER-4).
        try:
            pwned = await is_password_pwned(password)
        except HibpServiceError:
            await self._audit.log(
                AuditEventType.HIBP_CHECK_FAILED,
                ip_address=ip,
                event_data={"email_hash": _email_hash(email), "reason": "api_failure"},
            )
            pwned = False  # fail open — HIBP being down must not block registration

        if pwned:
            raise PasswordPolicyViolationError(
                "This password has appeared in a known data breach. Choose a different password."
            )

        existing = await self._users.find_by_email(email)
        if existing is not None:
            # Notify real owner without revealing this to the caller
            await self._email.send(
                to=email,
                subject="TradeForge: registration attempt on your account",
                html_body=(
                    "<p>Someone tried to create a TradeForge account with your email address.</p>"
                    "<p>If this was you, you already have an account — "
                    '<a href="#">log in here</a>.</p>'
                    "<p>If this was not you, no action is needed.</p>"
                ),
            )
            return  # identical response to successful registration

        password_hash = _ph.hash(password)
        user = await self._users.create(email=email, password_hash=password_hash)

        raw_token = generate_verification_token()
        token_hash = sha256_hex(raw_token)
        expires_at = datetime.now(timezone.utc) + EMAIL_VERIFICATION_TTL
        await self._verifications.create(
            email=email, token_hash=token_hash, expires_at=expires_at
        )

        await self._email.send(
            to=email,
            subject="Verify your TradeForge email address",
            html_body=(
                f"<p>Welcome to TradeForge!</p>"
                f"<p>Verify your email: <strong>{raw_token}</strong></p>"
                f"<p>This link expires in 24 hours.</p>"
            ),
        )
        # Prevent session creation before email is verified — user.is_email_verified stays False
        _ = user  # user stored; verification required before login is allowed

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------

    async def verify_email(self, raw_token: str, ip: str) -> None:
        # Per-IP rate limit (BLOCKER-3): prevents token-guessing brute force.
        ip_count = await self._sessions.increment_auth_attempts_ip(ip)
        if ip_count > IP_ATTEMPT_THRESHOLD:
            raise RateLimitedError("Too many requests from this IP.")

        token_hash = sha256_hex(raw_token)
        row = await self._verifications.find_by_token_hash(token_hash)
        now = datetime.now(timezone.utc)
        if row is None or row.expires_at.replace(tzinfo=timezone.utc) < now:
            raise InvalidTokenError("Verification token is invalid or expired.")

        user = await self._users.find_by_email(row.email)
        if user is None:
            raise InvalidTokenError("Verification token is invalid or expired.")

        await self._users.set_email_verified(user.id)
        await self._verifications.delete(row.id)  # single-use

        await self._audit.log(
            AuditEventType.EMAIL_VERIFIED,
            ip_address=ip,
            user_id=user.id,
        )

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(
        self, email: str, password: str, ip: str, user_agent: str | None
    ) -> tuple[uuid.UUID, str]:
        """Returns (user_id, session_token).

        Raises:
            RateLimitedError — per-IP threshold exceeded (429)
            AccountLockedError — per-account threshold exceeded (423)
            InvalidCredentialsError — wrong credentials (401)
            EmailNotVerifiedError — email not yet verified (403)
            RedisUnavailableError — Redis down (503)
        """
        # 1. Per-IP rate limit
        ip_count = await self._sessions.increment_ip_attempts(ip)
        if ip_count > IP_ATTEMPT_THRESHOLD:
            raise RateLimitedError("Too many login attempts from this IP.")

        # 2. Load user
        user = await self._users.find_by_email(email)

        if user is None:
            # Timing-safe: perform a dummy verify so "user not found" ≈ "wrong password" time
            try:
                _ph.verify(_DUMMY_HASH, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                pass
            await self._audit.log(
                AuditEventType.LOGIN_FAILURE,
                ip_address=ip,
                event_data={"reason": "user_not_found", "email_hash": _email_hash(email)},
            )
            raise InvalidCredentialsError()

        # 3. Per-account brute-force check (before verifying password — avoids timing leak)
        failure_count = await self._sessions.get_login_failures(_email_hash(email))
        if failure_count >= LOGIN_FAILURE_THRESHOLD or user.is_locked:
            await self._audit.log(
                AuditEventType.ACCOUNT_LOCKED,
                ip_address=ip,
                user_id=user.id,
            )
            raise AccountLockedError()

        # 4. Verify password
        try:
            _ph.verify(user.password_hash, password)
        except VerifyMismatchError:
            count = await self._sessions.increment_login_failures(_email_hash(email))
            event_data: dict[str, object] = {"reason": "wrong_password"}
            if count >= LOGIN_FAILURE_THRESHOLD:
                event_data["threshold_reached"] = True
                await self._audit.log(
                    AuditEventType.ACCOUNT_LOCKED,
                    ip_address=ip,
                    user_id=user.id,
                    event_data=event_data,
                )
            await self._audit.log(
                AuditEventType.LOGIN_FAILURE,
                ip_address=ip,
                user_id=user.id,
                event_data={"reason": "wrong_password"},
            )
            raise InvalidCredentialsError()
        except (VerificationError, InvalidHashError) as exc:
            raise InvalidCredentialsError() from exc

        # 5. Email must be verified before login is allowed
        if not user.is_email_verified:
            raise EmailNotVerifiedError()

        # 6. Reset failure counter on success
        await self._sessions.reset_login_failures(_email_hash(email))

        # 7. Rehash if needed (e.g. parameters changed)
        if _ph.check_needs_rehash(user.password_hash):
            new_hash = _ph.hash(password)
            await self._users.update_password(user.id, new_hash)

        # 8. Create new session token (SR-AUTH-007: session-fixation prevention)
        session_token = generate_session_token()
        await self._sessions.create_session(
            token=session_token,
            user_id=str(user.id),
            ip=ip,
            ua_hash=_ua_hash(user_agent),
        )

        await self._audit.log(
            AuditEventType.LOGIN_SUCCESS,
            ip_address=ip,
            user_id=user.id,
            user_agent=user_agent,
        )

        return user.id, session_token

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    async def logout(self, session_token: str, user_id: uuid.UUID, ip: str) -> None:
        await self._sessions.delete_session(session_token, str(user_id))
        await self._audit.log(
            AuditEventType.SESSION_INVALIDATED,
            ip_address=ip,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    async def request_password_reset(self, email: str, ip: str) -> None:
        """Always returns None — enumeration prevention (SR-AUTH-004)."""
        # Per-IP rate limit (BLOCKER-3): prevents reset-email flooding.
        ip_count = await self._sessions.increment_auth_attempts_ip(ip)
        if ip_count > IP_ATTEMPT_THRESHOLD:
            raise RateLimitedError("Too many requests from this IP.")

        await self._audit.log(
            AuditEventType.PASSWORD_RESET_REQUESTED,
            ip_address=ip,
            event_data={"email_hash": _email_hash(email)},
        )

        user = await self._users.find_by_email(email)
        if user is None:
            return  # identical response to valid email case

        # Invalidate any outstanding reset tokens for this account
        await self._resets.delete_by_email(email)

        raw_token = generate_reset_token()
        token_hash = sha256_hex(raw_token)
        expires_at = datetime.now(timezone.utc) + PASSWORD_RESET_TTL

        await self._resets.create(email=email, token_hash=token_hash, expires_at=expires_at)

        await self._email.send(
            to=email,
            subject="TradeForge: password reset request",
            html_body=(
                f"<p>We received a password reset request for your account.</p>"
                f"<p>Reset token: <strong>{raw_token}</strong></p>"
                f"<p>This token expires in 1 hour. If you did not request this, ignore this email.</p>"
            ),
        )

    async def confirm_password_reset(self, raw_token: str, new_password: str, ip: str) -> None:
        token_hash = sha256_hex(raw_token)
        row = await self._resets.find_by_token_hash(token_hash)
        now = datetime.now(timezone.utc)
        if row is None or row.expires_at.replace(tzinfo=timezone.utc) < now:
            raise InvalidTokenError("Reset token is invalid or expired.")

        policy_error = validate_password_policy(new_password)
        if policy_error is not None:
            raise PasswordPolicyViolationError(policy_error)

        # HIBP check (BLOCKER-4): service failure → log HIBP_CHECK_FAILED, fail open.
        try:
            pwned = await is_password_pwned(new_password)
        except HibpServiceError:
            await self._audit.log(
                AuditEventType.HIBP_CHECK_FAILED,
                ip_address=ip,
                event_data={"email_hash": _email_hash(row.email), "reason": "api_failure"},
            )
            pwned = False  # fail open

        if pwned:
            raise PasswordPolicyViolationError(
                "This password has appeared in a known data breach. Choose a different password."
            )

        user = await self._users.find_by_email(row.email)
        if user is None:
            raise InvalidTokenError("Reset token is invalid or expired.")

        new_hash = _ph.hash(new_password)
        await self._users.update_password(user.id, new_hash)
        await self._resets.delete(row.id)  # single-use

        # Full session revocation on password change (SR-AUTH-010)
        await self._sessions.revoke_all_user_sessions(str(user.id))

        await self._audit.log(
            AuditEventType.PASSWORD_RESET_COMPLETED,
            ip_address=ip,
            user_id=user.id,
        )
        await self._audit.log(
            AuditEventType.PASSWORD_CHANGED,
            ip_address=ip,
            user_id=user.id,
        )
