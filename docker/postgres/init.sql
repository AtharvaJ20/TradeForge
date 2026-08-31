-- TradeForge PostgreSQL initialisation — runs once on first container start.
--
-- Executed by the Docker entrypoint as the 'postgres' superuser, before any
-- application code or Alembic migrations run. This is the only file in the
-- repository where superuser-only operations are performed. Three categories
-- of work happen here:
--
--   1. Application user creation
--   2. Schema-level privileges that Alembic migrations require
--   3. PostgreSQL extensions that the application schema depends on
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ AFTER running 'alembic upgrade head' for the first time, apply the      │
-- │ table-level DML grants below as the postgres superuser. These cannot    │
-- │ run here because the tables do not exist until migrations create them.  │
-- │                                                                          │
-- │   docker exec tradeforge-postgres psql -U postgres -d tradeforge_dev    │
-- │                                                                          │
-- │   GRANT SELECT, INSERT, UPDATE, DELETE                                  │
-- │     ON ALL TABLES IN SCHEMA public TO tradeforge_app;                   │
-- │   REVOKE DELETE, UPDATE, TRUNCATE                                        │
-- │     ON security_audit_log FROM tradeforge_app;                          │
-- │   GRANT INSERT ON security_audit_log TO tradeforge_app;                 │
-- │   GRANT SELECT ON security_audit_log TO tradeforge_audit;               │
-- │                                                                          │
-- │ These enforce ADR-002's INSERT-only audit log requirement in local dev.  │
-- └─────────────────────────────────────────────────────────────────────────┘

-- ---------------------------------------------------------------------------
-- 1. Application users
-- ---------------------------------------------------------------------------

CREATE USER tradeforge_app   WITH PASSWORD 'dev_password';
CREATE USER tradeforge_audit WITH PASSWORD 'dev_password';

-- ---------------------------------------------------------------------------
-- 2. Schema-level privileges
-- ---------------------------------------------------------------------------

-- PostgreSQL 15 revoked CREATE on the public schema from PUBLIC by default.
-- tradeforge_app must be able to create tables, indexes, and sequences via
-- Alembic migrations.
GRANT CREATE ON SCHEMA public TO tradeforge_app;

-- If any migration is ever run as the postgres superuser (e.g. during an
-- initial bootstrap before DATABASE_URL is set), tables created by postgres
-- will not automatically grant REFERENCES to tradeforge_app. Without
-- REFERENCES, tradeforge_app cannot declare FK constraints pointing at those
-- tables in subsequent migrations.
--
-- ALTER DEFAULT PRIVILEGES is the correct mechanism: it applies to all future
-- tables created by postgres in this schema, not just the ones that exist now.
-- (GRANT REFERENCES ON ALL TABLES is a point-in-time statement and is a no-op
-- at init time because no tables exist yet.)
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT REFERENCES ON TABLES TO tradeforge_app;

-- ---------------------------------------------------------------------------
-- 3. PostgreSQL extensions
-- ---------------------------------------------------------------------------

-- btree_gist — required before 'alembic upgrade head' can run.
--
-- Migration 0002 (trade domain tables) uses an EXCLUSION constraint on
-- lot_size_history to prevent overlapping effective periods for the same
-- instrument. The constraint mixes instrument_id (WITH =) and daterange
-- (WITH &&) in a single GiST index. btree_gist enables GiST indexes over
-- btree-comparable types (UUID, DATE) that are not natively GiST-indexable.
--
-- Installing extensions requires superuser. tradeforge_app cannot do this.
-- If this extension is absent when migration 0002 runs, the migration will
-- fail with: ERROR: data type uuid has no default operator class for access
-- method "gist".
CREATE EXTENSION IF NOT EXISTS btree_gist;
