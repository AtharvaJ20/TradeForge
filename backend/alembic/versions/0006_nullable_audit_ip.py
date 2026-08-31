"""Make security_audit_log.ip_address nullable.

Service-layer audit events (e.g., from background jobs or test contexts)
have no associated HTTP request and therefore no client IP. Storing a
sentinel string like 'unknown' is rejected by the PostgreSQL INET type;
NULL is the correct representation of an unknown IP.

Revision ID: f1a2b3c4d5e6
Revises: e8c3a6f2d1b9
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e8c3a6f2d1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "security_audit_log",
        "ip_address",
        existing_type=sa.dialects.postgresql.INET(),
        nullable=True,
    )


def downgrade() -> None:
    # Set any NULL rows to '0.0.0.0' before re-adding NOT NULL constraint.
    op.execute(
        "UPDATE security_audit_log SET ip_address = '0.0.0.0' WHERE ip_address IS NULL"
    )
    op.alter_column(
        "security_audit_log",
        "ip_address",
        existing_type=sa.dialects.postgresql.INET(),
        nullable=False,
    )
