"""Migration 0010 — import_records table.

Adds the import_records table that tracks each broker CSV import run.
One row per import attempt; (file_hash, account_id) is unique to prevent
re-importing the same file into the same account.

Revision chain: 0009 (c9d5e4f3a2b1) → 0010 (f2a8b7c6d5e4)
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a8b7c6d5e4"
down_revision: Union[str, None] = "c9d5e4f3a2b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trading_accounts.id"),
            nullable=False,
        ),
        sa.Column("broker", sa.String(20), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_import_records_broker",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETE', 'PARTIAL', 'EMPTY', 'FAILED')",
            name="ck_import_records_status",
        ),
    )
    op.create_unique_constraint(
        "uq_import_records_hash_account",
        "import_records",
        ["file_hash", "account_id"],
    )
    op.create_index("idx_import_records_account_id", "import_records", ["account_id"])


def downgrade() -> None:
    op.drop_index("idx_import_records_account_id", table_name="import_records")
    op.drop_constraint("uq_import_records_hash_account", "import_records", type_="unique")
    op.drop_table("import_records")
