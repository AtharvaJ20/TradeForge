"""API layer — FastAPI routers, request/response Pydantic schemas, dependency injection.

Owns: HTTP request parsing, response serialization, route handlers, FastAPI dependencies.
Does NOT own: business logic, domain rules, DB queries.

Pydantic schemas live here (API contracts). They are NOT domain models.
Domain models live in the domain layer. The api layer maps between them.
"""
