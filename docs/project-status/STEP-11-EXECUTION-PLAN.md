# Step 11 — Broker Import + TradingAccount Introduction Execution Plan

**Author:** Krishna (Project Manager)
**Created:** 2026-09-01
**Status:** Ready for pre-decisions — implementation blocked on WS-0 outputs
**Depends on:** Step 10 complete ✅ (CI gate GREEN, Sahadeva GO, Yudhishthira ACCEPTED — 2026-09-01)
**ADR governing:** ADR-005 (TradingAccount deferred from Step 10; Step 11 is the binding point)

---

## Objective

When Step 11 is complete:

- A `trading_accounts` table exists and `account_id` is wired into `trades`, `execution_fills`, and `trade_pnl` as a nullable FK, with a follow-on migration promoting it to `NOT NULL` after backfill.
- A user can upload a Zerodha trade-day CSV and have fills ingested, reconstructed into trades, and P&L calculated — all attributed to a named trading account they selected at import time.
- Karna (Step 12) can begin designing analytics queries against a schema that has `account_id` present from day one.
- The broker adapter interface is defined and isolated so Upstox and Angel One adapters can be added without changing the import pipeline.

---

## Exact Scope

### In scope

| Area | Deliverable |
|---|---|
| Schema — new table | `trading_accounts` table per ADR-005 migration spec |
| Schema — FK additions | Nullable `account_id` on `trades`, `execution_fills`, `trade_pnl` |
| Schema — index additions | `idx_trading_accounts_user_id`, `idx_trades_account_id`, `idx_execution_fills_account_id`, `idx_trade_pnl_account_id` |
| Schema — NOT NULL promotion | Follow-on migration once all rows are backfilled (local dev: seed a dev account and backfill) |
| Domain | `TradingAccount` domain entity, `ImportRecord` value object, `BrokerAdapterPort` Protocol |
| Application — import pipeline | `ImportService`: validate → parse → deduplicate → ingest fills → reconstruct trades → calculate P&L |
| Application — account CRUD | `TradingAccountService`: create, list, get by id (owner-scoped) |
| Infrastructure — adapter | `ZerodhaAdapter` implementing `BrokerAdapterPort` (trade-day CSV format) |
| Infrastructure — adapter interface | `BrokerAdapterPort` Protocol; `NormalizedFill` value object as the contract |
| Infrastructure — import repo | `ImportRecordRepository`: store import metadata + original file reference |
| API | `POST /v1/accounts` (create account), `GET /v1/accounts` (list), `POST /v1/accounts/{id}/import` (upload CSV) |
| Backfill | `PnlService.backfill_all_closed` invoked as final step of import pipeline to cover any fills that closed existing open trades |
| Local dev backfill | Seed a default dev trading account; backfill `account_id = NULL` rows on `trade_pnl`, `trades`, `execution_fills` |

### Explicitly out of scope

| Item | Deferred to | Authority |
|---|---|---|
| Upstox and Angel One CSV adapters | Step 11-B or Phase 2 | Sanjaya — add after Zerodha adapter is stable |
| Broker API integrations (real-time, OAuth) | Phase 2 | REQUIREMENTS.md §8; §38 Phase 1 |
| Account-specific brokerage rates in `charge_schedules` | Phase 2 | ADR-005 Q1 |
| `journal_entries.account_id` | Post–Step 11 (optional) | Journal is a read-subscriber — no FK required for Phase 1 |
| Deposit / withdrawal tracking on accounts | Post–Step 11 | REQUIREMENTS.md §7 — not needed for import pipeline |
| Time zone and base currency per account | Post–Step 11 | Schema has `base_currency`; no application logic needed in Step 11 |
| Account isolation in analytics | Step 12 (Karna) | Karna builds account-filtered queries |
| Frontend import UI | Step 11-B or Step 12 | API-first for Step 11; no Arjun work until Bhima's API is stable |
| `orders` entity (raw broker orders) | Deferred | Traceability §9 gap — Phase 2 |
| Production S3 for import file storage | Pre-deployment | `StubStorage` pattern for file reference; real storage wired by Nakula |

---

## Pre-conditions (All Met)

| Pre-condition | Status |
|---|---|
| Step 10 P&L engine complete and CI-gated | ✅ |
| ADR-005 accepted — `TradingAccount` boundary defined | ✅ |
| `execution_fills.broker` is VARCHAR — no FK target yet | ✅ (correct Phase 1 state) |
| `trade_pnl` rows have `account_id = NULL` (local dev) | ✅ (expected; Step 11 backfills) |
| No Step 12 analytics work has begun | ✅ (Karna gate: must not start until Step 11 `account_id` FK is confirmed in schema) |

---

## Decisions Required Before Implementation (WS-0)

All three decisions must be resolved and on record before Bhima writes a line of Step 11 code. They can be resolved in a single session.

---

### WS-0 Decision 1 — Sanjaya + Ganesha: Zerodha CSV Format + NormalizedFill Contract

**Question:** Define the exact Zerodha trade-day CSV column layout and the `NormalizedFill` value object that `ZerodhaAdapter` produces.

**Required outputs:**
- Column list for Zerodha trade-day CSV (`symbol`, `exchange`, `trade_type`, `buy_qty`, `sell_qty`, `buy_avg_price`, `sell_avg_price`, `trade_date`, `order_id`, `trade_id`)
- `NormalizedFill` value object (fields, types, nullability) — this is the contract between any adapter and the import pipeline; it must map cleanly onto `execution_fills` columns
- Duplicate detection strategy: what constitutes a duplicate fill (broker trade_id + account_id? import run idempotency key?)
- Edge cases Sanjaya knows about: multi-leg option spreads in Zerodha CSV, expiry-day auto-square-off fills, after-market orders (AMO) timestamps

**Owner:** Sanjaya (format spec, edge cases) + Ganesha (confirm `NormalizedFill` contract maps correctly onto `execution_fills` domain rules)

**Blocks:** WS-2.1 (Domain layer), WS-2.2 (Infrastructure adapter)

---

### WS-0 Decision 2 — Mayasura: Confirm `trading_accounts` Schema vs ADR-005 Spec

**Question:** The ADR-005 migration spec (lines 99–127) defines the `trading_accounts` DDL and FK additions. Confirm this spec is final before Bhima writes the migration, or issue amendments.

**Specific open points:**
1. `account_type VARCHAR(20)` — should this be an enum constraint (`CHECK (account_type IN ('INDIVIDUAL','HUF','PROP'))`) or left as open varchar for Phase 1?
2. `status VARCHAR(10) DEFAULT 'ACTIVE'` — is a CHECK constraint needed on `status`?
3. `NOT NULL` promotion migration: should it live in the same migration file as a second step, or as a separate `0009_account_id_not_null.py`? (Recommendation: separate migration, applied only after backfill is verified.)
4. Does `journal_entries` need `account_id` in Step 11, or is `journal_entries` → `trades` → `trading_accounts` join sufficient for Phase 1? (Recommendation: skip direct FK — join is sufficient.)

**Owner:** Mayasura
**Blocks:** WS-1 (DB migrations)

---

### WS-0 Decision 3 — Bhima: Migration Numbering

**Question:** Migrations `0001`–`0007` exist. Confirm next available number is `0008` and confirm there are no locally applied uncommitted migrations that would create a conflict.

**Owner:** Bhima — check `alembic history` and confirm in migration header comment
**Blocks:** WS-1 (DB migrations) — low risk, confirmatory only

---

## Implementation Sequence

### WS-1 — Database Layer (Bhima) · Blocked on WS-0

#### WS-1.1 — Migration 0008: `trading_accounts` table + FK additions

Per ADR-005 spec (amended by Mayasura Decision 2 if needed):

```
CREATE TABLE trading_accounts (...)
ALTER TABLE trades           ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id)
ALTER TABLE execution_fills  ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id)
ALTER TABLE trade_pnl        ADD COLUMN account_id UUID NULL REFERENCES trading_accounts(id)
CREATE INDEX idx_trading_accounts_user_id         ON trading_accounts (user_id)
CREATE INDEX idx_trades_account_id                ON trades           (account_id)
CREATE INDEX idx_execution_fills_account_id       ON execution_fills  (account_id)
CREATE INDEX idx_trade_pnl_account_id             ON trade_pnl        (account_id)
```

**Acceptance criterion:** `alembic upgrade head` succeeds on a clean database. `account_id` is nullable on all three tables. No existing tests break.

#### WS-1.2 — Migration 0009: Local dev backfill + NOT NULL promotion

Applies only to local dev environments. Production application deferred until first production import confirms all rows are covered.

Steps:
1. INSERT a default dev `trading_accounts` row (seeded `user_id` from dev fixtures)
2. UPDATE `trades`, `execution_fills`, `trade_pnl` SET `account_id = <dev_account_id>` WHERE `account_id IS NULL`
3. ALTER TABLE `trades`, `execution_fills`, `trade_pnl` ALTER COLUMN `account_id` SET NOT NULL

**Note:** In production, step 3 (NOT NULL) must not be applied until after the first import populates all rows. Migration 0009 should carry a header comment warning: *"Apply step 3 only after backfill is confirmed. In production, run as a separate DBA operation after verifying zero NULL rows."*

**ORM updates:** Update `TradePnlModel`, `TradeFillModel`, `TradeModel` SQLAlchemy models to include `account_id: Mapped[Optional[UUID]]` after migration 0008, then `Mapped[UUID]` after migration 0009.

---

### WS-2 — Domain + Adapter Design (Sanjaya + Ganesha + Bhima) · Blocked on WS-0 Decision 1

#### WS-2.1 — Domain Layer (Bhima)

New file: `backend/src/tradeforge/domain/import_domain/`

- `types.py`:
  - `TradingAccount` domain entity (id, user_id, broker, display_name, account_type, base_currency, status)
  - `NormalizedFill` value object (from Sanjaya Decision 1 — represents one broker execution after adapter transformation)
  - `ImportRecord` value object (import_id, account_id, broker, file_hash, row_count, status, imported_at)
- `errors.py`:
  - `AccountNotFoundError`
  - `DuplicateImportError` (same file hash + account already imported)
  - `InvalidFillError` (fill fails domain validation)
  - `AdapterNotFoundError` (no adapter registered for broker string)

**Domain law (ADR-001):** Zero framework imports. No SQLAlchemy, no FastAPI. Pure Python only.

#### WS-2.2 — BrokerAdapterPort Protocol (Sanjaya design, Bhima implements)

New file: `backend/src/tradeforge/infrastructure/adapters/broker_adapter_port.py`

```python
class BrokerAdapterPort(Protocol):
    def parse(self, file_content: bytes) -> list[NormalizedFill]: ...
    def detect(self, file_content: bytes) -> bool: ...  # returns True if this adapter recognises the file
```

**Constraint:** `BrokerAdapterPort` is in infrastructure (not domain) because it deals with raw bytes. `NormalizedFill` (the output type) is in domain. The adapter produces domain value objects — no infrastructure types cross the domain boundary.

New file: `backend/src/tradeforge/infrastructure/adapters/zerodha_adapter.py`

Implements `BrokerAdapterPort`:
- `detect`: checks for Zerodha-specific header columns
- `parse`: reads CSV, validates columns, maps to `NormalizedFill` list; raises `InvalidFillError` on any unresolvable row

---

### WS-3 — Application Layer (Bhima) · Blocked on WS-2

Sequential: WS-3.1 → WS-3.2 → WS-3.3

#### WS-3.1 — `TradingAccountService`

Location: `backend/src/tradeforge/application/trading_account_service.py`

Methods:
- `create(user_id: UUID, broker: str, display_name: str, account_type: str, base_currency: str) → TradingAccount`
- `list(user_id: UUID) → list[TradingAccount]`
- `get(user_id: UUID, account_id: UUID) → TradingAccount` — raises `AccountNotFoundError` if not owned by user

**Authorization:** Every method takes `user_id` from session — never from request body. Follows same pattern as all existing services.

#### WS-3.2 — `ImportService`

Location: `backend/src/tradeforge/application/import_service.py`

Methods:
- `import_fills(user_id: UUID, account_id: UUID, file_content: bytes) → ImportSummary`

Execution sequence inside `import_fills`:
1. Verify `account_id` belongs to `user_id` (raises `AccountNotFoundError` if not)
2. Compute `file_hash`; check `ImportRecordRepository` for duplicate — raise `DuplicateImportError` if found
3. Detect broker from account's `broker` field; select adapter; call `adapter.parse(file_content)` → `list[NormalizedFill]`
4. For each `NormalizedFill`: validate domain rules (Ganesha); write to `execution_fills` with `account_id` set
5. Run `ReconstructionEngine.reconstruct_for_user(user_id)` — reconstruct trades from newly added fills
6. Run `PnlService.backfill_all_closed(user_id=user_id)` — calculate P&L for any newly closed trades
7. Write `ImportRecord` row (file_hash, row_count, account_id, status=COMPLETE)
8. Return `ImportSummary` (fills_ingested, trades_created, trades_closed, pnl_rows_created, duplicate_fills_skipped)

**Idempotency:** If a fill with the same broker fill ID + account_id already exists in `execution_fills`, skip it (duplicate detection at fill level, not only at file level).

**Error handling:** If `adapter.parse` raises for a subset of rows, collect errors and return partial summary with error list — do not abort the entire import. If a fill write fails a CHECK constraint, log at WARNING and skip that fill.

#### WS-3.3 — Wire `account_id` into existing `ReconstructionEngine`

Existing reconstruction engine in `application/trade/reconstruction.py` assigns fills to trades by `user_id` and instrument. After Step 11, newly imported fills carry `account_id`. The engine must propagate `account_id` from fill → trade when creating or updating a trade.

**Change scope:** Minimal. `account_id` is set from the fill at trade creation time. The reconstruction engine does not need to "know" about accounts — it just copies the field from fill to trade. Bhima must assess whether any reconstruction query filters need to be updated to be account-aware.

**Important:** Do not change any existing reconstruction logic for trade matching, FIFO, or P&L — only thread `account_id` through.

---

### WS-4 — API Layer (Bhima) · Blocked on WS-3

New router: `backend/src/tradeforge/api/v1/accounts.py`

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/v1/accounts` | POST | Session | Create a new trading account |
| `/v1/accounts` | GET | Session | List all trading accounts for the authenticated user |
| `/v1/accounts/{account_id}` | GET | Session | Get a single trading account (must be owned by user) |
| `/v1/accounts/{account_id}/import` | POST | Session | Upload a broker CSV and trigger import pipeline |

**Request/response shapes:** Define Pydantic v2 schemas for all endpoints. `account_id` in path; `user_id` always from session token.

**Import endpoint:** accepts `multipart/form-data` with a single file field. Returns `ImportSummary` JSON.

**Wire into `main.py`:** Include the new router under `/v1/accounts`.

---

### WS-5 — QA Validation (Sahadeva) · Starts after WS-4 is complete

WS-5 and the NOT-NULL migration (WS-1.2 step 3) can proceed in parallel once WS-4 is stable.

#### Test Group A — TradingAccount unit tests (domain layer)

| Test | Coverage |
|---|---|
| `TradingAccount` entity creation — valid fields | Domain types |
| `TradingAccount` — unknown broker string rejected | Domain validation |
| `NormalizedFill` — required fields missing → `InvalidFillError` | Domain validation |

#### Test Group B — ZerodhaAdapter unit tests (infrastructure layer)

| Test | Coverage |
|---|---|
| `detect()` returns True on well-formed Zerodha CSV | Adapter identification |
| `detect()` returns False on non-Zerodha file | Negative case |
| `parse()` — valid CSV → correct `NormalizedFill` list | Happy path |
| `parse()` — malformed row → `InvalidFillError` with row number | Error reporting |
| `parse()` — expiry-day auto-square-off row maps correctly | Zerodha edge case |
| `parse()` — AMO order timestamp normalized to exchange time | Timestamp edge case |

#### Test Group C — ImportService integration tests (application layer, real DB)

| Test | Coverage |
|---|---|
| CSV import → fills written → trades reconstructed → P&L rows created | Full happy path |
| Second upload of same file → `DuplicateImportError` returned | Idempotency |
| Duplicate fill row (same broker fill ID) in second CSV → skipped, summary reflects skip count | Fill-level dedup |
| Import to wrong account (different user) → `AccountNotFoundError` | Authorization |
| CSV with one invalid row → partial import succeeds, error list returned | Partial import |
| `account_id` is set correctly on `execution_fills`, `trades`, `trade_pnl` | ADR-005 compliance |

#### Test Group D — Account API integration tests

| Test | Coverage |
|---|---|
| `POST /v1/accounts` → 201 + created account | Create account |
| `GET /v1/accounts` → list scoped to authenticated user only | Authorization isolation |
| `POST /v1/accounts/{id}/import` → 200 + `ImportSummary` | Import API |
| `POST /v1/accounts/{id}/import` — account not owned by user → 404 | Authorization |

#### ADR-005 Compliance Verification

| Check | Why |
|---|---|
| Every `execution_fills` row after import has non-NULL `account_id` | Import path enforces account attribution |
| Every `trades` row reconstructed from import has non-NULL `account_id` | Account propagated from fills |
| Every `trade_pnl` row from import-triggered P&L has non-NULL `account_id` | P&L inherits account from trade |
| `charge_schedules` table has no `account_id` column | ADR-005 Q1: broker-level rates only in Phase 1 |
| `trading_accounts` RLS not yet required | Phase 2 per deferred items |

#### Acceptance Gate

Sahadeva issues "Go" / "Go with risks [list]" / "No Go" covering:
- All test groups A–D passing
- ADR-005 compliance verification passing
- `backfill_all_closed` integration confirmed (fills that close existing open trades result in P&L rows)
- `ImportSummary` counts are accurate on every test fixture

**No Step 12 (Karna analytics) work begins until Sahadeva issues "Go" or "Go with risks" on Step 11.**

---

## Dependency Graph

```
WS-0: Sanjaya (Decision 1 — NormalizedFill + CSV format)
WS-0: Mayasura (Decision 2 — schema confirmation)      ──► WS-1 (DB migrations)
WS-0: Bhima (Decision 3 — migration numbering)                    │
                                                                   ▼
WS-0 Decision 1 ──────────────────────────────────────► WS-2 (Domain + Adapter)
                                                                   │
                                                                   ▼
                                                           WS-3 (Application)
                                                                   │
                                                                   ▼
                                                            WS-4 (API)
                                                                   │
                                                     ┌─────────────┘
                                                     ▼
                                              WS-5 (QA)
                                                     │
                                                     ▼
                                              Step 11 DONE
                                      → Step 12 (Karna) unblocked
```

WS-1 and WS-2 can proceed in parallel once WS-0 decisions are resolved. WS-3 is sequential after WS-2. WS-4 is sequential after WS-3.

---

## Agent Assignments

| Workstream | Agent | Lane |
|---|---|---|
| WS-0 Decision 1 — NormalizedFill contract + CSV format | **Sanjaya** | Broker integration |
| WS-0 Decision 1 — domain rule validation of NormalizedFill | **Ganesha** | Trading domain |
| WS-0 Decision 2 — schema confirmation | **Mayasura** | Architecture |
| WS-0 Decision 3 — migration numbering | **Bhima** | Backend |
| WS-1 — DB migrations (0008, 0009) | **Bhima** | Backend |
| WS-2.1 — Domain layer (`TradingAccount`, `NormalizedFill`, `ImportRecord`, errors) | **Bhima** | Backend |
| WS-2.2 — `BrokerAdapterPort` Protocol + `ZerodhaAdapter` | **Bhima** | Backend |
| WS-3.1 — `TradingAccountService` | **Bhima** | Backend |
| WS-3.2 — `ImportService` | **Bhima** | Backend |
| WS-3.3 — `account_id` threading into `ReconstructionEngine` | **Bhima** | Backend |
| WS-4 — API router (`/v1/accounts`) | **Bhima** | Backend |
| WS-5 — All QA test groups | **Sahadeva** | QA |
| QA release recommendation | **Sahadeva** | QA |

**Arjun:** No frontend work in Step 11. The import and account management UI is deferred to Step 11-B. API-first delivery allows Karna to begin analytics design without a frontend.

**Nakula:** No infrastructure changes in Step 11. Real file storage for import files (`StubStorage` / real S3) activates at first production deployment. Nakula's backfill responsibilities activate at production deployment.

**Mayasura:** Only WS-0 Decision 2 (schema sign-off). If any implementation surprise contradicts ADR-005 during Step 11, escalate to Mayasura before proceeding — do not unilaterally amend the schema.

**Karna:** Do not begin writing analytics queries until Sahadeva's Step 11 "Go" recommendation is on record. The gate exists because Karna's queries must see `account_id` in schema from day one.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Zerodha CSV format has undocumented edge cases that break adapter at parse time | Medium | Medium — import silently drops fills | Sanjaya documents known edge cases in WS-0 Decision 1; Sahadeva writes negative test cases for each one |
| `ReconstructionEngine` threading of `account_id` touches more code than expected | Medium | Medium — scope creep into WS-3.3 | Bhima scopes WS-3.3 before starting WS-3.2; if significant, Mayasura must review before implementation |
| Migration 0009 `NOT NULL` promotion applied to production before all rows backfilled | Low | High — blocking incident, column rejects INSERTs | Migration 0009 carries a header warning; Nakula owns the production backfill verification gate |
| `PnlService.backfill_all_closed` re-calculates rows that were already calculated — idempotency risk | Low | Low — upsert logic already handles ON CONFLICT | Confirmed by Step 10 TC-G3-006; no change needed |
| `DuplicateImportError` triggers on re-upload of a corrected file (user intent was to replace, not re-import) | Medium | Low — user experience friction | Define file-level idempotency key as hash + account_id; document that re-upload of a corrected file requires a support flow in Phase 1 |
| Sanjaya Decision 1 turns up that Zerodha CSV uses multiple formats across trade types (EQ vs F&O) | Medium | Medium — one adapter must handle both or two sub-adapters needed | Sanjaya to confirm in WS-0; if two formats exist, design one `ZerodhaAdapter` with internal dispatch before any code is written |
| `orders` entity gap (traceability §9) becomes a blocker when Zerodha CSV includes order-level columns | Low | Medium — order_id field orphaned if no `orders` table | `NormalizedFill` stores `order_reference` as an opaque string; no FK to an `orders` table in Phase 1. If order-level analytics are required, flag as a Phase 2 item. |

---

## Deferred Items

| Item | Why Deferred | Phase |
|---|---|---|
| Upstox + Angel One adapters | Zerodha first; adapters are isolated — add without pipeline changes | Phase 1-B |
| Import preview / column-mapping UI | Frontend deferred for API-first delivery | Step 11-B |
| Deposit / withdrawal tracking per account | Not needed for import pipeline in Phase 1 | Phase 2 |
| Account-specific brokerage rates | ADR-005 Q1 explicit decision | Phase 2 |
| `journal_entries.account_id` direct FK | Journal joins through trades; direct FK adds no value in Phase 1 | Phase 2 |
| PostgreSQL RLS on `trading_accounts` | Not implemented until Phase 2 per existing deferred risk | Phase 2 |
| Real-time broker API sync | Phase 1 scope is CSV only | Phase 2 |

---

## Definition of Done — Step 11

- [ ] WS-0 Decision 1: Sanjaya `NormalizedFill` contract documented and Ganesha-confirmed
- [ ] WS-0 Decision 2: Mayasura schema sign-off on `trading_accounts` DDL (with amendments if any)
- [ ] Migration 0008 applied: `trading_accounts` table + nullable `account_id` on `trades`, `execution_fills`, `trade_pnl`; all four indexes created
- [ ] Migration 0009 applied (local dev): dev account seeded, `account_id` backfilled, NOT NULL promoted
- [ ] `TradingAccount` domain entity, `NormalizedFill`, `ImportRecord`, domain errors — zero framework imports
- [ ] `BrokerAdapterPort` Protocol defined in infrastructure layer
- [ ] `ZerodhaAdapter` — `detect()` and `parse()` implemented; all Sanjaya edge cases handled
- [ ] `TradingAccountService` — create, list, get; `user_id` always from session
- [ ] `ImportService` — full 8-step pipeline; idempotency at file and fill level
- [ ] `ReconstructionEngine` threads `account_id` from fills to trades
- [ ] `/v1/accounts` router wired into `main.py`
- [ ] All Sahadeva Test Groups A–D passing
- [ ] ADR-005 compliance verification passing (account_id non-null after import; charge_schedules unchanged)
- [ ] `TRADEFORGE-CURRENT-STATE.md` updated to reflect Step 11 complete

---

*Krishna — Senior Project Manager*
*Domain inputs: Mayasura (ADR-005), Sanjaya (broker integration), Ganesha (trade domain), Bhima (backend), Sahadeva (QA)*
*Implementation owner: Bhima*
*QA owner: Sahadeva*
*Adapter spec owner: Sanjaya*
*Architecture sign-off: Mayasura*
