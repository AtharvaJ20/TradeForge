"""Application settings — loaded once at startup from environment variables.

Production: env vars are injected by AWS Secrets Manager / ECS task definition.
Local dev:  env vars are loaded from .env by the uvicorn launch command
            (`uvicorn tradeforge.main:app --env-file ../.env`), or by the
            caller explicitly loading python-dotenv before importing this module.

No default values are provided for security-sensitive settings. Missing required
vars raise a clear error at startup rather than silently using an insecure default.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env is loaded by the process launcher, not here, to keep the
        # settings class environment-agnostic. Set env_file only if you need
        # to load it inside the process (e.g., in test conftest).
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis
    redis_url: str

    # AWS KMS (broker credential envelope encryption — ADR-002)
    kms_key_arn: str
    kms_endpoint_url: str = ""  # empty = real AWS; set to LocalStack URL for local dev

    # Transactional email
    email_transport: str  # "smtp" | "resend"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    resend_api_key: str = ""
    from_address: str = ""

    # CORS — comma-separated list of allowed origins (no wildcards — ADR-002)
    allowed_origins: str

    # Application secret (token signing, etc.)
    secret_key: str

    # Cookie security: True in production (HTTPS), False for local HTTP dev
    secure_cookies: bool = True

    # Comma-separated IPs/CIDRs of trusted reverse proxies (e.g. load balancers).
    # Only these peers are allowed to supply an X-Forwarded-For header that is
    # trusted for client-IP extraction (BLOCKER-2). Empty = no trusted proxies
    # (local dev default — use direct peer IP).
    trusted_proxies: str = ""

    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()
