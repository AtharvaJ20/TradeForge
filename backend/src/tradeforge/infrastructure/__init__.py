"""Infrastructure layer — all external system concerns.

Owns: SQLAlchemy ORM models, database session factory, Redis client,
      AWS KMS client, email senders, repository implementations.

Allowed imports: domain layer, sqlalchemy, asyncpg, redis, boto3, pydantic (for
      data mapping only — NOT for domain models).
Forbidden imports: fastapi (use dependency injection via api layer instead).
"""
