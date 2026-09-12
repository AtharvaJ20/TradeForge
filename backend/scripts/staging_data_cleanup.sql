-- DEF-DASH-006: Staging data cleanup
-- Removes all user-owned business data (QA test contamination) while
-- preserving: user accounts, auth state, reference data, and charge schedules.
--
-- USAGE:
--   psql "$DATABASE_URL" -f staging_data_cleanup.sql
--
-- TABLES PRESERVED (auth + reference data):
--   users, pending_email_verifications, pending_password_resets,
--   security_audit_log, instruments, lot_size_history, charge_schedules
--
-- TABLES CLEANED (user-owned business data):
--   trading_accounts, trades, execution_fills, management_events, tax_lots,
--   fill_exclusions, trade_pnl, journal_entries, journal_attachments,
--   journal_audit_log, import_records
--
-- SAFETY: TRUNCATE ... CASCADE handles FK ordering automatically.
-- Run inside a transaction so the whole operation is atomic.

BEGIN;

-- Sanity check: show counts before deletion
SELECT 'trading_accounts' AS tbl, COUNT(*) FROM trading_accounts
UNION ALL SELECT 'trades',           COUNT(*) FROM trades
UNION ALL SELECT 'execution_fills',  COUNT(*) FROM execution_fills
UNION ALL SELECT 'trade_pnl',        COUNT(*) FROM trade_pnl
UNION ALL SELECT 'journal_entries',  COUNT(*) FROM journal_entries
UNION ALL SELECT 'import_records',   COUNT(*) FROM import_records;

-- Truncate all user-owned data in dependency-safe order via CASCADE
TRUNCATE
    journal_attachments,
    journal_audit_log,
    journal_entries,
    fill_exclusions,
    tax_lots,
    trade_pnl,
    execution_fills,
    management_events,
    trades,
    import_records,
    trading_accounts
CASCADE;

-- Confirm all cleared
SELECT 'trading_accounts' AS tbl, COUNT(*) FROM trading_accounts
UNION ALL SELECT 'trades',           COUNT(*) FROM trades
UNION ALL SELECT 'journal_entries',  COUNT(*) FROM journal_entries;

COMMIT;
