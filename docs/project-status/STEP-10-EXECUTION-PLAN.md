# Step 10 — P&L Engine Execution Plan

**Author:** Krishna (Project Manager)
**Created:** 2026-08-24
**Last updated:** 2026-08-24 — revised after ADR-005 acceptance
**Status:** Ready for implementation — two pre-decisions still required (Ganesha, Kubera)
**Depends on:** Steps 1–9 complete (all confirmed done)

---

## Objective

Implement the Step 10 P&L calculation engine that populates `trade_pnl` for every closed trade. When Step 10 is complete:

- Every trade that transitions to `CLOSED` has a `trade_pnl` row with gross P&L, net P&L, itemised charges, and R-multiple.
- The journal's `PnlStatus` transitions from `PENDING_CALCULATION` to `AVAILABLE` for real trade data.
- Karna (Step 12) has the `trade_pnl` data it needs to run analytics.
- QA has validated all 9 test cases defined in `JOURNAL-PNL-INTEGRATION.md`.

---

## Architecture Decisions Governing Step 10

All decisions below are **Accepted**. Step 10 implementation must not contradict them.

| ADR | Decision | Impact on Step 10 |
|---|---|---|
| ADR-001 | Python / FastAPI / SQLAlchemy / Decimal | Domain layer has zero framework imports; Decimal arithmetic only |
| ADR-003 | `trade_pnl` is Option A (separate table); journal is read-only subscriber | `JournalRepository` never writes `trade_pnl`; Step 10 engine owns all writes |
| **ADR-005** | `TradingAccount` deferred to Step 11; `charge_schedules` stays broker-string-based for Phase 1; account-specific brokerage rates are Phase 2 | `trade_pnl` does **not** receive `account_id` in Step 10. `charge_schedules` is keyed by `(broker, trade_type, exchange, effective_from)` — no `account_id` column. The Phase 2 extension point (account-specific rates taking precedence over broker defaults) must not be closed by the Step 10 schema. |

**ADR-005 Q1 is resolved:** broker-level charge schedules are accepted for Phase 1. All users on the same broker share one rate schedule. No action required before Step 10.

---

## What Is Already Done

| Artifact | State |
|---|---|
| `trade_pnl` stub ORM (`infrastructure/models/trade_pnl.py`) | Exists — summary columns only; needs expansion |
| Migration `0004` — `trade_pnl` stub | Applied locally (summary + identity columns only) |
| `JOURNAL-PNL-INTEGRATION.md` | Complete spec: full schema, trigger rules, recalculation rules, back-fill rules, 9 test cases |
| Kubera `SKILL.md` | Complete P&L formulas: gross P&L by instrument type, all 7 charge components, R-multiple |
| `JournalRepository` reads 4 summary columns | Already implemented — no journal changes needed |
| `PnlStatus` domain type and `PnlSnapshot` | Already implemented in journal domain |

---

## Pre-Implementation Decisions Still Required

Two decisions remain open. Both must be resolved before Bhima writes a line of Step 10 code. They can be resolved in the same session.

### Decision 1 — Ganesha: Confirm FIFO is Not a Step 10 Blocker

**Question:** Do the two unresolved FIFO items (Unresolved 4: multi-lot CNC FIFO; Unresolved 5: NRML_FUT incremental lot FIFO) block Step 10's P&L formula?

**Expected answer:** No. Step 10 reads `trades.average_entry` and `trades.average_exit` as computed by the reconstruction engine. In Phase 1, reconstruction already produces correct single-lot FIFO for CNC (trivially satisfied — one open lot per instrument at a time) and average cost for NRML_FUT. Step 10 does not need to re-do lot tracking.

**Owner:** Ganesha
**Required output:** Written confirmation that Phase 1 Step 10 may treat `trades.average_entry` / `trades.average_exit` as its authoritative inputs without re-solving lot attribution.

---

### Decision 2 — Kubera: `charge_schedules` Table Schema and Seed Data

**Question:** Define the `charge_schedules` table schema and provide initial Zerodha seed data sufficient to pass TC-G3-001 through TC-G3-009.

**Constraints from ADR-005:**
- Primary key / lookup key: `(broker, trade_type, exchange, effective_from)` — no `account_id` column.
- Broker is a string: `ZERODHA | UPSTOX | ANGEL_ONE | MANUAL`.
- The schema must leave room for a future nullable `account_id` FK without a destructive migration (e.g., do not define a UNIQUE constraint that would be violated by adding account rows later).

**Required output:**
- Column definitions for `charge_schedules` (brokerage rate/flat cap, STT rates by side, exchange transaction charges by segment/exchange, SEBI rate, stamp duty rate, IPFT rate, effective-from date, broker, trade_type, exchange)
- Migration DDL
- Initial seed rows for Zerodha (all 4 trade types: MIS EQ, CNC EQ, NRML_FUT, NRML_OPT — NSE segment, effective from a known date)

**Owner:** Kubera

---

### Decision 3 — Bhima: Migration Strategy for `trade_pnl` Expansion *(Can be decided at implementation start)*

**Question:** Edit migration `0004` (Option 1) or add migration `0005` (Option 2)?

**Recommendation:** Option 1 — edit `0004` and reset the local database. No production environment exists; no applied migration needs protecting. Editing `0004` produces a cleaner schema history with no temporary `DEFAULT '0.0.0'` scaffolding.

**If local DB cannot be reset:** use Option 2 (`0005` with temporary defaults as documented in `JOURNAL-PNL-INTEGRATION.md` Section 12).

**Owner:** Bhima — decide and document in the migration header comment.

---

## Implementation Sequence

### WS-1 — Pre-decisions · Blocks all other workstreams

| Task | Owner | Output |
|---|---|---|
| Confirm FIFO non-blocker (Decision 1) | Ganesha | Written confirmation |
| `charge_schedules` schema + seed data (Decision 2) | Kubera | DDL + seed rows |
| Migration strategy (Decision 3) | Bhima | Comment in migration file |

WS-2 and WS-3 cannot start until Decisions 1 and 2 are resolved. Decision 3 can be finalised at the start of WS-2.1.

---

### WS-2 — Backend Implementation (Bhima) · Sequential

All tasks are sequential — each depends on the one above.

#### WS-2.1 — Database Layer

**Task A: Expand `trade_pnl` schema**

Per `JOURNAL-PNL-INTEGRATION.md` Section 3.5. Add:
- Columns: `calculated_at`, `engine_version`, `brokerage`, `stt`, `exchange_charges`, `sebi_charges`, `stamp_duty`, `gst`, `ipft`, `charge_schedule_version`, `broker`
- CHECK constraints: `total_charges` identity (`= brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst + ipft`), all charge components `>= 0`
- Index: `idx_trade_pnl_user_id`
- Update `TradePnl` ORM model to match

**No `account_id` column.** Per ADR-005, `account_id` is introduced in Step 11. The `broker` column (VARCHAR) is the authoritative broker identifier for Step 10.

**Task B: `charge_schedules` table**

- Migration DDL from Kubera (Decision 2)
- Lookup key: `(broker, trade_type, exchange, effective_from)` — broker-string-based, no `account_id`
- UNIQUE constraint: `(broker, trade_type, exchange, effective_from)` — this constraint must not prevent a future nullable `account_id` FK from being added. If Kubera's design uses a partial unique index instead of a table-level constraint, note that preference.
- Seed Zerodha rates for all 4 Phase 1 trade types (Bhima's call on seed mechanism: alembic data migration or standalone seed script)

**Acceptance criteria:** `alembic upgrade head` succeeds against a clean database. `charge_schedules` contains Zerodha rates for all 4 trade types. `trade_pnl` schema matches Section 3.5 of `JOURNAL-PNL-INTEGRATION.md` exactly.

---

#### WS-2.2 — Domain Layer

**Task: `PnlCalculator` domain service**

- Location: `backend/src/tradeforge/domain/pnl/`
- Files: `calculator.py`, `types.py`, `errors.py`
- `types.py`: `ChargeSchedule` value object (all rate fields from `charge_schedules`), `TradeSnapshot` value object, `PnlResult` value object (all `trade_pnl` fields), `PnlEngineVersion = "1.0.0"` constant
- `calculator.py`: pure functions, no I/O:
  - `compute_gross_pnl(trade_snapshot, lot_size) → Decimal` — per instrument type and direction (Kubera Sections 3–4)
  - `compute_charges(trade_snapshot, charge_schedule) → ChargeBreakdown` — all 7 components, no intermediate rounding
  - `compute_r_multiple(net_pnl, planned_risk_amount) → Decimal | None`
  - `compute_pnl(trade_snapshot, charge_schedule, lot_size, planned_risk_amount) → PnlResult`
- `errors.py`: `PnlCalculationError`, `ChargeScheduleNotFoundError`, `LotSizeNotFoundError`

**Domain law (ADR-001):** Zero framework imports. Pure Python Decimal only. Fully unit-testable without a database.

**`ChargeSchedule` value object carries broker as a string.** It does not carry `account_id`. This is correct per ADR-005 and must not be changed in Step 10.

**Acceptance criteria:** All Kubera Section 13 test groups pass as unit tests. The full worked example from Kubera Section 8 (Zerodha MIS NSE equity: gross ₹2,500, total charges ₹92.74, net ₹2,407.26) passes exactly. GST base excludes STT and stamp duty — verified in a dedicated test.

---

#### WS-2.3 — Infrastructure Layer

**Task A: `ChargeScheduleRepository`**

- Location: `backend/src/tradeforge/infrastructure/repositories/charge_schedule_repo.py`
- Single method: `get_for_date(broker: str, trade_type: TradeType, exchange: str, trade_date: date) → ChargeSchedule`
- Lookup: latest row where `broker = $1 AND trade_type = $2 AND exchange = $3 AND effective_from <= $trade_date`, ordered by `effective_from DESC LIMIT 1`
- Raises `ChargeScheduleNotFoundError` if no row matches

**Signature is broker-string-based.** Per ADR-005: no `account_id` parameter in Phase 1. If account-specific rates are introduced in Phase 2, this method signature will gain an optional `account_id` parameter with a fallback to broker-level rows. That extension is deferred; do not pre-build it now.

**Task B: `PnlRepository` (write side)**

- Location: `backend/src/tradeforge/infrastructure/repositories/pnl_repo.py`
- Methods:
  - `upsert(pnl_result: PnlResult) → None` — INSERT ON CONFLICT (trade_id) DO UPDATE for all columns
  - `get_planned_risk(trade_id: UUID) → Decimal | None` — SELECT `planned_risk_amount` from `journal_entries` (read-only cross-domain read, permitted per `JOURNAL-PNL-INTEGRATION.md` Section 11.2)

`JournalRepository.has_pnl_row()` and `get_pnl_snapshot()` already exist and are unchanged.

---

#### WS-2.4 — Application Layer

**Task: `PnlService`**

- Location: `backend/src/tradeforge/application/pnl_service.py`
- Methods:
  - `calculate_and_store(trade_id: UUID) → None` — full execution sequence per `JOURNAL-PNL-INTEGRATION.md` Section 5.3. Logs at WARNING and returns silently on any precondition failure. Never raises to the caller.
  - `recalculate_r_multiple(trade_id: UUID) → None` — lightweight recalculation per Section 9.3. Updates only `r_multiple`, `updated_at`, `calculated_at`.
  - `backfill_all_closed(user_id: UUID | None = None) → int` — runs back-fill query per Section 8.2, calls `calculate_and_store` for each unprocessed closed trade, returns count processed.
- Engine version: `PnlEngineVersion` constant from domain layer (`"1.0.0"`)

**Precondition checks in `calculate_and_store` (all 6 must pass):**

| # | Check | Failure action |
|---|---|---|
| 1 | `trades.status = 'CLOSED'` | Log + return |
| 2 | `trades.average_entry IS NOT NULL` | Log + return |
| 3 | `trades.average_exit IS NOT NULL` | Log + return |
| 4 | `trades.total_entry_quantity > 0` | Log + return |
| 5 | Charge schedule exists for `broker + trade_type + trade_date` | Log + return |
| 6 | Lot size exists for `instrument_id + trade_date` (NRML_FUT, NRML_OPT only) | Log + return |

**Broker for charge schedule lookup** is read from `execution_fills.broker` (string) — not from any account entity. Per ADR-005, this is correct for Phase 1.

---

#### WS-2.5 — Wire BackgroundTask Triggers

**Trigger 1: Trade close → P&L calculation**

- Locate where `trades.status` transitions to `CLOSED` in `reconstruction.py`
- After the status write, queue: `background_tasks.add_task(pnl_service.calculate_and_store, trade.id)`
- `PnlService` is injected as a dependency (application layer to application layer — permitted)

**Trigger 2: `planned_stop` updated → R-multiple recalculation**

- In `JournalService.upsert_entry`, after writing a new `planned_risk_amount`
- If `trades.status = CLOSED` and a `trade_pnl` row exists, queue: `background_tasks.add_task(pnl_service.recalculate_r_multiple, trade_id)`
- The journal service does not call `PnlService` synchronously — it queues only

**Acceptance criteria:** Integration test — a request that closes a trade (or triggers reconstruction to close a trade) results in a `trade_pnl` row in the DB within the same request lifecycle. The row's `broker` column matches `execution_fills.broker` for that trade.

---

### WS-3 — QA Validation (Sahadeva) · Starts after WS-2.4 is complete

WS-2.5 and WS-3 can run in parallel once WS-2.4 is complete.

#### Test Group A — Unit tests on `PnlCalculator` (domain layer)

| Test | Source |
|---|---|
| Equity long gross P&L — single fill/exit, sign correct | Kubera Section 3 |
| Equity short gross P&L — sign inversion confirmed | Kubera Section 3 |
| Futures gross P&L — lot size applied | Kubera Section 3 |
| Options buyer gross P&L — ITM and expires worthless | Kubera Section 3 |
| Weighted average entry — multiple fills | Kubera Section 1 |
| Full charge calculation — Zerodha MIS NSE: ₹92.74 total, ₹2,407.26 net | Kubera Section 8 |
| GST base excludes STT and stamp duty | Kubera Section 7 |
| `total_charges` identity holds to 4 decimal places | TC-G3-003 |
| R-multiple: profitable trade (+0.60R) | Kubera Section 12 |
| R-multiple: clean stop-out (−1R) | Kubera Section 12 |
| R-multiple: `planned_risk_amount = 0` → NULL | TC-G3-005 |

#### Test Group B — Integration tests on `PnlService`

| Test | Source |
|---|---|
| New closed trade, no journal entry → row inserted, `r_multiple` NULL | TC-G3-001 |
| Closed trade with `planned_stop` set → `r_multiple` computed | TC-G3-002 |
| Step 10 runs twice for same trade → idempotent ON CONFLICT | TC-G3-006 |
| Step 10 skips OPEN trade → no row inserted | TC-G3-007 |
| Charge identity violated → CHECK constraint rejects INSERT | TC-G3-009 |
| `planned_stop` set after row exists → lightweight recalc updates `r_multiple` | TC-G3-004 |
| Back-fill query returns only orphaned closed trades | TC-G3-008 |

#### Additional Verification (from ADR-005)

| Check | Why |
|---|---|
| `trade_pnl.broker` matches `execution_fills.broker` on every inserted row | Confirms charge schedule lookup used fill-level broker, not any account entity |
| `trade_pnl` has no `account_id` column | Confirms Step 11 schema boundary was not violated |
| `charge_schedules` has no `account_id` column | Confirms broker-level rate model per ADR-005 Q1 |

#### Acceptance Gate

Sahadeva issues a QA recommendation ("Go" / "Go with risks [list]" / "No Go") covering:
- All Group A unit tests passing
- All Group B integration tests passing
- ADR-005 verification checks passing
- `total_charges` identity holds on every test fixture
- `PnlStatus` transitions correctly observed in journal response (PENDING_CALCULATION → AVAILABLE)
- R-multiple nullability rules verified for all 4 null conditions (Section 7.2)

**No Step 11 work begins until Sahadeva issues a "Go" or "Go with risks" recommendation on Step 10.**

---

## Dependency Graph

```
WS-1: Ganesha (Decision 1) ─┐
WS-1: Kubera (Decision 2)   ├──► WS-2.1 (DB Layer)
WS-1: Bhima (Decision 3)   ─┘         │
                                       ▼
                                 WS-2.2 (Domain)
                                       │
                                       ▼
                                 WS-2.3 (Infra)
                                       │
                                       ▼
                                 WS-2.4 (Application)
                                       │
                             ┌─────────┴───────────┐
                             ▼                     ▼
                       WS-2.5 (Wire)         WS-3 (QA)
                             │                     │
                             └─────────┬───────────┘
                                       ▼
                                  Step 10 DONE
                                  → Step 11 unblocked
                                  (Step 11 introduces TradingAccount
                                   and adds account_id to trade_pnl)
```

WS-2 is strictly sequential. WS-2.5 and WS-3 can run in parallel once WS-2.4 is complete.

---

## Agent Assignments

| Workstream | Agent | Lane |
|---|---|---|
| Decision 1 — FIFO confirmation | **Ganesha** | Trading domain |
| Decision 2 — `charge_schedules` schema + seed | **Kubera** | P&L specification |
| Decision 3 — migration strategy | **Bhima** | Backend |
| WS-2.1 — DB migrations + ORM | **Bhima** | Backend |
| WS-2.2 — Domain `PnlCalculator` | **Bhima** | Backend |
| WS-2.3 — Infrastructure repositories | **Bhima** | Backend |
| WS-2.4 — `PnlService` application layer | **Bhima** | Backend |
| WS-2.5 — BackgroundTask wiring | **Bhima** | Backend |
| WS-3 — QA validation (all test groups) | **Sahadeva** | QA |
| QA release recommendation | **Sahadeva** | QA |

**Arjun:** No frontend work in Step 10. The journal UI already handles all four `PnlStatus` states. A charge breakdown view is deferred to Phase 2 per `JOURNAL-PNL-INTEGRATION.md`.

**Nakula:** No infrastructure changes in Step 10. Back-fill is a local operational task run by Bhima. Nakula's back-fill responsibilities activate at first production deployment.

**Mayasura:** No new architectural decisions needed for Step 10. ADR-005 is accepted and governs all open questions. Any surprise that contradicts ADR-005 during implementation must be escalated to Mayasura before proceeding.

---

## Out of Scope (Step 10)

| Item | Deferred to | Authority |
|---|---|---|
| `account_id` on `trade_pnl`, `trades`, `execution_fills` | Step 11 | ADR-005 |
| `TradingAccount` entity | Step 11 | ADR-005 |
| Account-specific brokerage rates in `charge_schedules` | Phase 2 | ADR-005 Q1 |
| Partial trade P&L (PARTIAL status trades) | Phase 2 | Kubera |
| Futures daily MTM breakdown (per-day settlements) | Phase 2 | Kubera |
| Options exercise/assignment P&L | Deferred | Ganesha + Kubera |
| Corporate action retroactive P&L adjustment | Deferred | Unresolved 3 |
| Multi-lot CNC FIFO across simultaneous open trades | Deferred | Unresolved 4 |
| NRML_FUT incremental lot FIFO | Deferred | Unresolved 5 |
| Karna analytics queries on `trade_pnl` | Step 12 | Karna |
| Frontend charge breakdown view | Phase 2 | Arjun |
| Production S3, cloud infrastructure | Pre-deployment | Nakula |
| Broker import (fills to close trades end-to-end) | Step 11 | Sanjaya |
| PostgreSQL RLS on `trade_pnl` | Phase 2 | Bhima + Nakula |

---

## Blockers and Risks

| Blocker / Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Kubera `charge_schedules` schema is more complex than expected (e.g., per-turnover-tier brokerage) | Medium | High — delays WS-2.1 | Kubera scope-limits to flat + capped brokerage for Phase 1; tier pricing deferred |
| Ganesha FIFO confirmation reveals Step 10 needs to re-do lot attribution | Low | High — reconstruction rework required | Ganesha confirmation is first task; escalate to Atharva immediately if blocked |
| UNIQUE constraint on `charge_schedules` prevents Phase 2 `account_id` addition | Low | Medium — schema migration required in Phase 2 | Kubera uses a partial unique index or a composite key that accommodates a nullable `account_id` column later |
| Local DB migration conflict (0004 already applied, Option 1 chosen) | Medium | Low — local only | Use Option 2 (migration 0005) if reset is disruptive |
| BackgroundTask fails silently — P&L row not written despite HTTP 200 | Medium | Medium — test TC-G3-001 gives false confidence | Integration test must assert `trade_pnl` row exists in DB, not just HTTP 200 |
| Charge rates in seed data are incorrect | Low | Medium — wrong `net_pnl`, test fails | Sahadeva cross-checks against Kubera Section 8 worked example as the canonical fixture |

---

## Definition of Done — Step 10

- [ ] Ganesha FIFO confirmation written and on record
- [ ] Kubera `charge_schedules` schema and seed data finalised (broker-string-keyed, no `account_id`)
- [ ] `trade_pnl` ORM and migration fully expanded per `JOURNAL-PNL-INTEGRATION.md` Section 3.5 (no `account_id`)
- [ ] `charge_schedules` migration applied and seeded with Zerodha rates for all 4 trade types
- [ ] `PnlCalculator` domain service: Kubera Section 8 worked example passes exactly
- [ ] `PnlService.calculate_and_store` handles all 6 precondition failures without raising
- [ ] BackgroundTask trigger wired from reconstruction engine close
- [ ] BackgroundTask trigger wired from `JournalService.upsert_entry` → R-multiple recalculation path
- [ ] All 9 integration test cases (TC-G3-001 through TC-G3-009) passing
- [ ] All Kubera Section 13 test groups passing as unit tests
- [ ] ADR-005 verification checks passing (broker column correct, no `account_id` in schema)
- [ ] `total_charges` identity constraint verified on every test fixture
- [ ] Sahadeva QA recommendation issued: "Go" or "Go with risks [list]"
- [ ] `TRADEFORGE-CURRENT-STATE.md` updated to reflect Step 10 complete

---

*Krishna — Senior Project Manager*
*Domain inputs: Kubera (JOURNAL-PNL-INTEGRATION.md, SKILL.md), Ganesha (TRADE-DOMAIN-RULES.md, TRADE-RECONSTRUCTION-SPEC.md), Mayasura (ADR-001, ADR-003, ADR-005)*
*Implementation owner: Bhima*
*QA owner: Sahadeva*
