"""FastAPI application factory."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from tradeforge.domain.auth.errors import RedisUnavailableError
from tradeforge.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="TradeForge API",
        version="0.1.0",
        description="Indian-market trading journal and performance intelligence platform.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # CSRF protection: reject state-changing requests with a foreign Origin header.
    # SameSite=Strict handles the cross-site cookie case; this layer catches
    # non-browser clients that might try to forge cross-origin state mutations.
    @app.middleware("http")
    async def csrf_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("Origin")
            if origin is not None and origin not in settings.allowed_origins_list():
                # Best-effort CSRF_ATTEMPT audit log (SR-AUTH-018).
                # Wrapped in try/except so any DB failure cannot suppress the 403.
                try:
                    from tradeforge.api.v1.deps import get_client_ip
                    from tradeforge.domain.auth.events import AuditEventType
                    from tradeforge.infrastructure.db import create_session
                    from tradeforge.infrastructure.repositories.auth_repo import AuditLogRepository

                    ip: str = get_client_ip(request)

                    async with create_session() as session:
                        await AuditLogRepository(session).log(
                            AuditEventType.CSRF_ATTEMPT,
                            ip_address=ip,
                            event_data={
                                "origin": origin,
                                "path": str(request.url.path),
                                "method": request.method,
                            },
                        )
                        await session.commit()
                except Exception:  # noqa: S110
                    pass  # Never let audit failure suppress the 403
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF_VALIDATION_FAILED"},
                )
        response = await call_next(request)
        # Prevent all auth API responses from being cached
        if request.url.path.startswith("/v1/auth"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Global error handler: Redis unavailable → 503 (SR-AUTH-021 Rule D)
    @app.exception_handler(RedisUnavailableError)
    async def redis_unavailable_handler(
        request: Request, exc: RedisUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "SERVICE_UNAVAILABLE"})

    # Auth router
    from tradeforge.api.v1 import auth

    app.include_router(auth.router, prefix="/v1")

    # Journal router
    from tradeforge.api.v1 import journal

    app.include_router(journal.router, prefix="/v1")

    # Accounts router (Step 11 — trading accounts + broker import)
    from tradeforge.api.v1 import accounts

    app.include_router(accounts.router, prefix="/v1")

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
