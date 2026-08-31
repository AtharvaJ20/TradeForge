"""fill_exclusions: append-only exclusion list for E1 crossing-zero fills.

Adds one new table. No changes to any existing trade domain table.

fill_id references execution_fills(id) with a UNIQUE constraint — one
exclusion record per fill. excluded_by references users(id). The
replacement_fill_ids UUID array records which MANUAL fills replaced the
quarantined fill. Append-only enforcement: BEFORE UPDATE and BEFORE DELETE
triggers raise unconditionally — no exception path exists.

See: docs/design/TRADE-DOMAIN-DATA-MODEL.md (fill_exclusions section)
See: docs/design/TRADE-RECONSTRUCTION-SPEC.md §12 (E1)

Revision ID: c4e2f9a1d8b5
Revises: b7d4e2f8a1c3
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4e2f9a1d8b5"
down_revision: Union[str, None] = "b7d4e2f8a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # fill_exclusions
    #
    # Permanent exclusion list — the reconstruction engine's unprocessed-fill
    # query filters out any fill whose id appears here:
    #
    #   SELECT * FROM execution_fills
    #   WHERE trade_id IS NULL
    #     AND id NOT IN (SELECT fill_id FROM fill_exclusions)
    #
    # This preserves execution_fills immutability: the quarantined fill's row
    # is never touched. The exclusion is an external, durable record of why
    # the fill is permanently skipped and which MANUAL fills replace it.
    # ------------------------------------------------------------------
    op.create_table(
        "fill_exclusions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "fill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("execution_fills.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        # UUID array — IDs of the import_source='MANUAL' fills that replace
        # the excluded fill. Empty array is permitted on insert but the §12
        # operator workflow requires replacements to exist before reconstruction
        # is re-triggered.
        sa.Column(
            "replacement_fill_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column(
            "excluded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "excluded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        # One exclusion record per fill — critical correctness constraint.
        # Also serves as the FK index on fill_id (UNIQUE creates a B-tree index).
        sa.UniqueConstraint("fill_id", name="uq_fill_exclusions_fill_id"),
    )

    # FK index on excluded_by (users.id reference).
    op.create_index(
        "idx_fill_exclusions_excluded_by",
        "fill_exclusions",
        ["excluded_by"],
    )

    # ------------------------------------------------------------------
    # Append-only trigger — fill_exclusions
    #
    # Both UPDATE and DELETE are unconditionally forbidden. Unlike
    # execution_fills (which permits the NULL→value trade_id assignment),
    # fill_exclusions has no permitted mutation path at all after INSERT.
    # The entire row is the immutable audit record.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_fill_exclusions_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'fill_exclusions rows are permanent audit records: '
                    'DELETE is not permitted (exclusion id=%, fill_id=%).',
                    OLD.id, OLD.fill_id;
            END IF;

            -- UPDATE: no mutation path exists. Every column is immutable.
            RAISE EXCEPTION
                'fill_exclusions rows are immutable after insert: '
                'UPDATE is not permitted (exclusion id=%, fill_id=%).',
                OLD.id, OLD.fill_id;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_fill_exclusions_append_only
        BEFORE UPDATE OR DELETE ON fill_exclusions
        FOR EACH ROW EXECUTE FUNCTION trg_fill_exclusions_append_only()
        """
    )

    # ------------------------------------------------------------------
    # Grants
    #
    # SELECT and INSERT only — UPDATE and DELETE are already blocked by the
    # trigger, but withholding the privileges adds a second enforcement layer
    # consistent with the append-only design intent. The pattern differs from
    # 0002 (which grants all DML) because fill_exclusions has no legitimate
    # UPDATE or DELETE path, not even a soft-delete.
    # ------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT ON fill_exclusions TO tradeforge_app")


def downgrade() -> None:
    # Drop trigger and function before dropping the table.
    op.execute("DROP TRIGGER IF EXISTS trg_fill_exclusions_append_only ON fill_exclusions")
    op.execute("DROP FUNCTION IF EXISTS trg_fill_exclusions_append_only()")
    op.drop_table("fill_exclusions")
