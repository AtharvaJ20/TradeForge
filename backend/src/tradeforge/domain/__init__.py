"""Domain layer — pure Python, zero framework dependencies.

Allowed imports: Python stdlib only.
Forbidden imports: fastapi, pydantic, sqlalchemy, celery, redis, boto3, or
any other infrastructure or framework library.

This boundary is enforced by ADR-001. Domain layer tests must run without
a database connection, without starting the application, and without any
network access.
"""
