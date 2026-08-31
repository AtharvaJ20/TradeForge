"""Trade domain tables: instruments, lot_size_history, trades, execution_fills,
management_events, tax_lots. Includes immutability triggers and the btree_gist
EXCLUSION constraint on lot_size_history.

Revision ID: b7d4e2f8a1c3
Revises: a8f3c1d9e5b2
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d4e2f8a1c3"
down_revision: Union[str, None] = "a8f3c1d9e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Pre-requisite: btree_gist extension.
    # This extension is required by the lot_size_history EXCLUSION constraint
    # (it enables GiST indexes over btree-comparable types such as UUID and DATE).
    # It must be installed by a superuser BEFORE this migration runs.
    # For local dev: docker/postgres/init.sql installs it at container init time.
    # For production: the DBA/Nakula provisions it at RDS database setup time.
    # The application user (tradeforge_app) cannot create extensions.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # instruments
    # ------------------------------------------------------------------
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("exchange_segment", sa.String(20), nullable=False),
        sa.Column("instrument_type", sa.String(10), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("strike_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "exchange_segment IN ('NSE_EQ', 'NSE_FO', 'BSE_EQ')",
            name="ck_instruments_exchange_segment",
        ),
        sa.CheckConstraint(
            "instrument_type IN ('EQ', 'FUT', 'CE', 'PE')",
            name="ck_instruments_instrument_type",
        ),
    )

    # Three partial unique indexes implement Rule 5.1 identity constraints.
    # Standard UNIQUE with nullable columns would treat NULL as distinct and
    # allow spurious duplicate equity rows — partial indexes avoid this.
    op.create_index(
        "uq_instruments_eq",
        "instruments",
        ["symbol", "exchange_segment"],
        unique=True,
        postgresql_where=sa.text("instrument_type = 'EQ'"),
    )
    op.create_index(
        "uq_instruments_fut",
        "instruments",
        ["symbol", "exchange_segment", "expiry_date"],
        unique=True,
        postgresql_where=sa.text("instrument_type = 'FUT'"),
    )
    op.create_index(
        "uq_instruments_opt",
        "instruments",
        ["symbol", "exchange_segment", "expiry_date", "strike_price", "instrument_type"],
        unique=True,
        postgresql_where=sa.text("instrument_type IN ('CE', 'PE')"),
    )
    op.create_index(
        "idx_instruments_isin",
        "instruments",
        ["isin"],
        postgresql_where=sa.text("isin IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # lot_size_history
    # ------------------------------------------------------------------
    op.create_table(
        "lot_size_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column("lot_size", sa.Numeric(18, 4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "effective_from",
            name="uq_lsh_instrument_effective_from",
        ),
        sa.CheckConstraint("lot_size > 0", name="ck_lsh_lot_size_positive"),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_lsh_until_after_from",
        ),
    )
    op.create_index(
        "idx_lsh_instrument_until",
        "lot_size_history",
        ["instrument_id", "effective_until"],
    )

    # EXCLUSION constraint: prevents overlapping effective periods for the
    # same instrument. NULL effective_until is treated as 'infinity' via
    # COALESCE. '[)' half-open interval semantics: a row ending on date D
    # does not overlap a row starting on date D.
    op.execute(
        """
        ALTER TABLE lot_size_history
        ADD CONSTRAINT excl_lsh_no_overlap
        EXCLUDE USING gist (
            instrument_id WITH =,
            daterange(
                effective_from,
                COALESCE(effective_until, 'infinity'::date),
                '[)'
            ) WITH &&
        )
        """
    )

    # ------------------------------------------------------------------
    # trades
    # ------------------------------------------------------------------
    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column("trade_type", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("first_fill_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_fill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_entry_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "total_exit_quantity",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("net_position", sa.Numeric(18, 4), nullable=False),
        sa.Column("average_entry", sa.Numeric(18, 4), nullable=True),
        sa.Column("average_exit", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_entry", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_stop", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_target", sa.Numeric(18, 4), nullable=True),
        sa.Column("planned_risk_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("setup_name", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "trade_type IN ('MIS', 'CNC', 'CNC_SAME_DAY', 'NRML_FUT', 'NRML_OPT')",
            name="ck_trades_trade_type",
        ),
        sa.CheckConstraint("direction IN ('LONG', 'SHORT')", name="ck_trades_direction"),
        sa.CheckConstraint("status IN ('OPEN', 'PARTIAL', 'CLOSED')", name="ck_trades_status"),
        sa.CheckConstraint("net_position >= 0", name="ck_trades_net_position_gte0"),
        sa.CheckConstraint("total_entry_quantity >= 0", name="ck_trades_total_entry_gte0"),
        sa.CheckConstraint("total_exit_quantity >= 0", name="ck_trades_total_exit_gte0"),
        sa.CheckConstraint(
            "total_exit_quantity <= total_entry_quantity",
            name="ck_trades_exit_lte_entry",
        ),
    )
    op.create_index("idx_trades_user_status", "trades", ["user_id", "status"])
    op.create_index("idx_trades_user_date", "trades", ["user_id", "trade_date"])
    op.create_index(
        "idx_trades_user_instrument_status",
        "trades",
        ["user_id", "instrument_id", "status"],
    )
    op.create_index("idx_trades_instrument_id", "trades", ["instrument_id"])

    # ------------------------------------------------------------------
    # execution_fills
    # ------------------------------------------------------------------
    op.create_table(
        "execution_fills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=True,
        ),
        sa.Column("fill_role", sa.String(5), nullable=True),
        sa.Column("fill_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("session", sa.String(15), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("product_type", sa.String(10), nullable=False),
        sa.Column("exit_type", sa.String(20), nullable=True),
        sa.Column("order_id", sa.String(64), nullable=True),
        sa.Column("fill_id", sa.String(64), nullable=True),
        sa.Column("broker", sa.String(20), nullable=False),
        sa.Column("import_source", sa.String(10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "session IN ('PRE_OPEN', 'REGULAR', 'POST_CLOSE')",
            name="ck_fills_session",
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_fills_side"),
        sa.CheckConstraint(
            "fill_role IN ('ENTRY', 'EXIT') OR fill_role IS NULL",
            name="ck_fills_fill_role",
        ),
        sa.CheckConstraint("product_type IN ('MIS', 'CNC', 'NRML')", name="ck_fills_product_type"),
        sa.CheckConstraint("quantity > 0", name="ck_fills_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_fills_price_positive"),
        sa.CheckConstraint(
            "broker IN ('ZERODHA', 'UPSTOX', 'ANGEL_ONE', 'MANUAL')",
            name="ck_fills_broker",
        ),
        sa.CheckConstraint(
            "trade_id IS NOT NULL OR fill_role IS NULL",
            name="ck_fills_role_requires_trade",
        ),
        sa.CheckConstraint(
            "exit_type IS NULL OR fill_role = 'EXIT' OR fill_role IS NULL",
            name="ck_fills_exit_type_requires_exit_role",
        ),
    )
    op.create_index("idx_fills_trade_id", "execution_fills", ["trade_id"])
    op.create_index(
        "idx_fills_user_instrument_date",
        "execution_fills",
        ["user_id", "instrument_id", "trade_date"],
    )
    op.create_index("idx_fills_user_date", "execution_fills", ["user_id", "trade_date"])
    # Partial unique index: idempotent re-import guard (broker + fill_id, when fill_id known)
    op.create_index(
        "uq_fills_broker_fill_id",
        "execution_fills",
        ["broker", "fill_id"],
        unique=True,
        postgresql_where=sa.text("fill_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # Immutability trigger — execution_fills
    #
    # Enforces:
    #   1. BEFORE DELETE: always raises — fills are permanent records.
    #   2. BEFORE UPDATE: permits only the NULL→value transition on trade_id
    #      and fill_role (reconstruction assignment). All other column
    #      modifications are rejected. Prevents value→different-value
    #      reassignment once trade_id/fill_role are set.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_execution_fills_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'execution_fills rows are permanent: DELETE is not permitted (fill id=%).',
                    OLD.id;
            END IF;

            -- UPDATE: only the assignment of trade_id and fill_role (NULL → value) is allowed.
            IF NEW.user_id        IS DISTINCT FROM OLD.user_id        OR
               NEW.instrument_id  IS DISTINCT FROM OLD.instrument_id  OR
               NEW.fill_timestamp IS DISTINCT FROM OLD.fill_timestamp OR
               NEW.trade_date     IS DISTINCT FROM OLD.trade_date     OR
               NEW.session        IS DISTINCT FROM OLD.session        OR
               NEW.side           IS DISTINCT FROM OLD.side           OR
               NEW.quantity       IS DISTINCT FROM OLD.quantity       OR
               NEW.price          IS DISTINCT FROM OLD.price          OR
               NEW.product_type   IS DISTINCT FROM OLD.product_type   OR
               NEW.exit_type      IS DISTINCT FROM OLD.exit_type      OR
               NEW.order_id       IS DISTINCT FROM OLD.order_id       OR
               NEW.fill_id        IS DISTINCT FROM OLD.fill_id        OR
               NEW.broker         IS DISTINCT FROM OLD.broker         OR
               NEW.import_source  IS DISTINCT FROM OLD.import_source  OR
               NEW.created_at     IS DISTINCT FROM OLD.created_at
            THEN
                RAISE EXCEPTION
                    'execution_fills rows are immutable: only trade_id and fill_role '
                    'may be set (NULL → value). Attempted modification of other columns '
                    '(fill id=%).',
                    OLD.id;
            END IF;

            -- Prevent reassignment: once set, trade_id and fill_role cannot change.
            IF OLD.trade_id IS NOT NULL AND NEW.trade_id IS DISTINCT FROM OLD.trade_id THEN
                RAISE EXCEPTION
                    'execution_fills.trade_id cannot be changed once assigned '
                    '(fill id=%, existing trade_id=%).',
                    OLD.id, OLD.trade_id;
            END IF;
            IF OLD.fill_role IS NOT NULL AND NEW.fill_role IS DISTINCT FROM OLD.fill_role THEN
                RAISE EXCEPTION
                    'execution_fills.fill_role cannot be changed once assigned '
                    '(fill id=%, existing fill_role=%).',
                    OLD.id, OLD.fill_role;
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_fills_immutable
        BEFORE UPDATE OR DELETE ON execution_fills
        FOR EACH ROW EXECUTE FUNCTION trg_execution_fills_immutable()
        """
    )

    # ------------------------------------------------------------------
    # management_events
    # ------------------------------------------------------------------
    op.create_table(
        "management_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_level", sa.Numeric(18, 4), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "corrects_event_id",
            postgresql.UUID(as_uuid=True),
            # Self-referencing FK: deferred to allow INSERT of the row before
            # the corrects_event_id row is referenced within the same txn.
            # In practice inserts are sequential, but DEFERRABLE avoids
            # ordering constraints in bulk imports.
            sa.ForeignKey("management_events.id", deferrable=True, initially="DEFERRED"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ("
            "'STOP_MOVED_BREAKEVEN', 'STOP_TIGHTENED', 'STOP_WIDENED', "
            "'TARGET_ADJUSTED', 'SCALE_IN', 'DEFENSIVE_SCALE_OUT', "
            "'OVERNIGHT_HOLD_NOTED', 'NOTE_ADDED'"
            ")",
            name="ck_mgmt_event_type",
        ),
    )
    op.create_index("idx_mgmt_trade_id", "management_events", ["trade_id"])
    op.create_index("idx_mgmt_user_occurred", "management_events", ["user_id", "occurred_at"])
    # Partial index on corrects_event_id (WHERE NOT NULL): FK index +
    # used by the active-timeline EXISTS subquery in canonical queries.
    op.create_index(
        "idx_mgmt_corrects_event_id",
        "management_events",
        ["corrects_event_id"],
        postgresql_where=sa.text("corrects_event_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # Immutability trigger — management_events
    #
    # Body fields are immutable after INSERT. The only permitted mutations:
    #   - deleted_at: NULL → value (soft delete)
    # All other UPDATE attempts are rejected.
    # DELETE is blocked; soft delete via deleted_at is the only removal.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_management_events_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'management_events rows are permanent: DELETE is not permitted '
                    '(event id=%). Use soft delete (deleted_at = now()).',
                    OLD.id;
            END IF;

            -- UPDATE: only deleted_at is mutable (soft-delete path).
            IF NEW.trade_id          IS DISTINCT FROM OLD.trade_id          OR
               NEW.user_id           IS DISTINCT FROM OLD.user_id           OR
               NEW.event_type        IS DISTINCT FROM OLD.event_type        OR
               NEW.occurred_at       IS DISTINCT FROM OLD.occurred_at       OR
               NEW.price_level       IS DISTINCT FROM OLD.price_level       OR
               NEW.quantity          IS DISTINCT FROM OLD.quantity          OR
               NEW.notes             IS DISTINCT FROM OLD.notes             OR
               NEW.corrects_event_id IS DISTINCT FROM OLD.corrects_event_id OR
               NEW.created_at        IS DISTINCT FROM OLD.created_at
            THEN
                RAISE EXCEPTION
                    'management_events body fields are immutable after insert. '
                    'Only deleted_at may be set to soft-delete the row '
                    '(event id=%).',
                    OLD.id;
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_mgmt_events_immutable
        BEFORE UPDATE OR DELETE ON management_events
        FOR EACH ROW EXECUTE FUNCTION trg_management_events_immutable()
        """
    )

    # ------------------------------------------------------------------
    # tax_lots
    # ------------------------------------------------------------------
    op.create_table(
        "tax_lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id"),
            nullable=False,
        ),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("quantity_original", sa.Numeric(18, 4), nullable=False),
        sa.Column("quantity_remaining", sa.Numeric(18, 4), nullable=False),
        sa.Column("cost_per_share", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_id", name="uq_taxlots_trade_id"),
        sa.CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_CLOSED', 'CLOSED')",
            name="ck_taxlots_status",
        ),
        sa.CheckConstraint("quantity_remaining >= 0", name="ck_taxlots_remaining_gte0"),
        sa.CheckConstraint(
            "quantity_remaining <= quantity_original",
            name="ck_taxlots_remaining_lte_original",
        ),
        sa.CheckConstraint("quantity_original > 0", name="ck_taxlots_original_positive"),
        sa.CheckConstraint("cost_per_share > 0", name="ck_taxlots_cost_positive"),
    )
    op.create_index(
        "idx_taxlots_fifo",
        "tax_lots",
        ["user_id", "instrument_id", "status", "purchase_date"],
    )

    # ------------------------------------------------------------------
    # RLS grants — extend the grant applied after migration 0001.
    # tradeforge_app needs full access to all six new tables.
    # ------------------------------------------------------------------
    for table in (
        "instruments",
        "lot_size_history",
        "trades",
        "execution_fills",
        "management_events",
        "tax_lots",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO tradeforge_app")


def downgrade() -> None:
    # Drop triggers and functions before dropping tables (functions are not
    # table-owned; they must be dropped explicitly).
    op.execute("DROP TRIGGER IF EXISTS trg_mgmt_events_immutable ON management_events")
    op.execute("DROP FUNCTION IF EXISTS trg_management_events_immutable()")
    op.execute("DROP TRIGGER IF EXISTS trg_fills_immutable ON execution_fills")
    op.execute("DROP FUNCTION IF EXISTS trg_execution_fills_immutable()")

    # Drop tables in reverse dependency order.
    op.drop_table("tax_lots")
    op.drop_table("management_events")
    op.drop_table("execution_fills")
    op.drop_table("trades")
    op.drop_table("lot_size_history")
    op.drop_table("instruments")

    # btree_gist is a shared extension — do not drop it; other databases or
    # future migrations may depend on it. Dropping the extension is left
    # as a manual DBA operation if genuinely required.
