"""Application layer — use cases and orchestration.

Owns: business workflow coordination (calling domain logic + repositories).
Does NOT own: domain rules (domain layer), HTTP (api layer), DB queries (infrastructure layer).

Allowed imports: domain layer, infrastructure layer interfaces (abstract types only).
Forbidden imports: fastapi, sqlalchemy ORM models, raw DB sessions.
"""
