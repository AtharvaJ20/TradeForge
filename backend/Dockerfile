# ---- builder stage ----
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ---- runtime stage ----
FROM python:3.12-slim AS runtime
RUN useradd --no-create-home --shell /bin/false --uid 1001 appuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY alembic/ ./alembic/
COPY alembic.ini ./
USER appuser
# Railway injects $PORT; alembic runs migrations before uvicorn starts.
CMD ["sh", "-c", "alembic upgrade head && uvicorn tradeforge.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
