# Advanced Trading Journal — Product Requirements Document

**Document:** `REQUIREMENTS.md`  
**Status:** Team-Aligned Product Requirements  
**Version:** 1.1  
**Product Type:** Advanced trading journal and trading-performance intelligence platform

**Team Alignment:** This requirements document is aligned to the current 20-agent organization: Krishna (Project Manager), Yudhishthira (Product Manager), Mayasura (Software Architect), Usha (UI/UX), Arjuna (Frontend), Bhima (Backend), Nakula (DevOps/SRE), Hanuman (Security), Sahadeva (QA), Vishwakarma (ML/AI), Vyasa (Data Engineering), Narada (Data Science), Chitragupta (Data Analysis), Karna (Quant), Ganesha (Trading Domain), Sanjaya (Broker Integrations), Dhanvantari (Risk), Vidura (Trading Psychology), Kubera (P&L), and Drona (Learning & Growth support).

---

## 1. Product Vision

Build an advanced trading journal that does more than store trades.

The product should become a trader's **single source of truth for trading activity, performance, risk, behavior, and continuous improvement**.

The system should:

1. Capture trades accurately.
2. Reconstruct complete positions from orders/executions.
3. Calculate P&L, costs, risk, and performance deterministically.
4. Help traders understand which strategies, setups, instruments, and market conditions work.
5. Identify behavioral mistakes and recurring patterns.
6. Provide actionable risk and performance insights.
7. Support broker/API imports as well as manual and file-based imports.
8. Use AI for analysis and recommendations without allowing AI to become the source of truth for financial calculations.

---

# 2. Product Principles

## 2.1 Financial correctness first

All monetary, position, P&L, fee, and risk calculations must be deterministic, reproducible, and testable.

AI/ML must not directly modify authoritative financial records.

## 2.2 Data is the source of truth

The imported broker/execution data and validated user-entered data form the authoritative trading record.

Derived analytics should be calculated from this trusted data.

## 2.3 Journal first, analytics second

The product must preserve a clean raw trade history before applying analytics, classifications, or AI interpretation.

## 2.4 Explainable analytics

Every important metric should have a clear definition and, where practical, allow the user to drill down to the underlying trades.

## 2.5 Trader improvement over vanity metrics

The product should prioritize insights that help traders improve decision-making rather than only displaying attractive dashboards.

## 2.6 Extensible architecture

The system should support future expansion into multiple brokers, asset classes, markets, strategies, AI features, and mobile clients.

---

# 3. Target Users

## Primary Users

### Individual Active Trader

A trader who wants to journal, analyze, and improve their trading.

### Serious/Professional Trader

A trader with substantial trade volume who needs automation, broker synchronization, advanced analytics, and risk monitoring.

### Trading Coach / Mentor

A user who needs to review performance and behavioral patterns across a trader's history.

## Future Users

* Trading teams
* Proprietary trading desks
* Investment/trading education platforms
* Research-oriented traders

---

# 4. Supported Trading Scope

The architecture should be designed to support:

* Equities
* Futures
* Options
* ETFs
* Index instruments
* Currency instruments where applicable
* Crypto as a future extension

The first release may limit supported asset classes, but the data model must not prevent future expansion.

Trading styles:

* Intraday
* Swing
* Positional
* Scalping
* Systematic/algorithmic

---

# 5. Core Product Modules

The application should be organized into the following major modules:

1. Authentication & User Management
2. Trading Account Management
3. Trade Import & Broker Integrations
4. Order & Execution Management
5. Trade/Position Reconstruction
6. Journal
7. Performance Analytics
8. Risk Management
9. Strategy & Setup Management
10. Market Context
11. Trading Psychology
12. Dashboard
13. Reports
14. AI Trading Assistant
15. Notifications & Alerts
16. Administration
17. Audit & Data Integrity
18. Learning & Growth / Knowledge Enablement

---

# 6. Authentication & User Management

## Functional Requirements

The system must support:

* User registration
* Login/logout
* Password reset
* Email verification
* Session management
* Secure authentication
* User profile
* Time zone
* Base currency
* Trading preferences

Future support:

* Google OAuth
* Other OAuth providers
* MFA/2FA
* Passkeys

## Security Requirements

* Passwords must never be stored in plaintext.
* Sensitive credentials must be encrypted.
* Authentication tokens must be securely managed.
* Sessions must support expiration/revocation.
* Authorization must be enforced server-side.

---

# 7. Trading Account Management

Users must be able to create and manage multiple trading accounts.

Each account should store:

* Account name
* Broker
* Account type
* Base currency
* Starting capital
* Current balance
* Account status
* Time zone
* Account-specific fee configuration
* Account-specific trading rules

Example:

```text
Account
├── Broker
├── Currency
├── Starting Capital
├── Deposits
├── Withdrawals
├── Orders
├── Executions
├── Positions
└── Trades
```

A user must be able to isolate analytics by account or view consolidated performance.

---

# 8. Broker & Data Import

The product must support multiple ways of importing trading data.

## Import Methods

### Manual Entry

Users can manually create trades.

### CSV/Excel Import

Users can upload broker statements/files.

The import system should:

* Detect file format
* Validate columns
* Preview data
* Map columns
* Validate timestamps
* Detect duplicates
* Report errors
* Allow correction before final import
* Preserve the original import file/reference

### Broker APIs

Future integrations should support broker APIs.

The architecture must isolate broker-specific logic behind a common integration interface.

Example:

```text
Broker Adapter
      ↓
Normalized Order/Execution Model
      ↓
Trade Reconstruction Engine
      ↓
Journal
```

---

# 9. Order & Execution Management

The system must distinguish between:

* Orders
* Executions/fills
* Positions
* Completed trades

This distinction is critical.

A single order may have multiple executions.

A position may be built using multiple entries and exits.

A completed trade may contain:

* Multiple entry executions
* Multiple exit executions
* Partial fills
* Partial exits
* Scale-ins
* Scale-outs

The system must retain the underlying executions rather than flattening everything into a single record.

---

# 10. Trade Reconstruction Engine

The system must reconstruct logical trades from execution data.

Example:

```text
BUY 100 @ ₹100
BUY 100 @ ₹105
SELL 100 @ ₹115
SELL 100 @ ₹120
```

The system should correctly reconstruct the position and calculate:

* Quantity
* Weighted average entry
* Exit price
* Gross P&L
* Charges
* Net P&L
* Holding duration
* Remaining position

Trade matching rules must be explicit and configurable where required.

Supported concepts should include:

* FIFO where appropriate
* Average-cost methods where applicable
* Partial exits
* Scale-in
* Scale-out
* Multi-leg strategies
* Re-entry

---

# 11. Journal

Each completed or active trade should have a journal entry.

## Core Trade Fields

* Trade ID
* Account
* Instrument
* Symbol
* Asset class
* Direction
* Entry date/time
* Exit date/time
* Quantity
* Entry price
* Exit price
* Stop loss
* Target
* Gross P&L
* Fees
* Net P&L
* Risk amount
* R-multiple
* Holding time

## Journal Fields

* Strategy
* Setup
* Setup type
* Market condition
* Entry reason
* Exit reason
* Trade thesis
* Planned entry
* Planned stop
* Planned target
* Mistakes
* Emotions
* Confidence
* Discipline score
* Notes
* Tags
* Screenshots
* Attachments

The journal must support editing and version/audit history for important changes.

---

# 12. Strategy & Setup Management

Users should be able to create reusable strategies and setups.

Example:

```text
Strategy: Breakout Trading

Setups:
- Opening Range Breakout
- Consolidation Breakout
- Volume Breakout
```

Each strategy/setup should have:

* Name
* Description
* Rules
* Entry conditions
* Exit conditions
* Stop rules
* Target rules
* Tags

Analytics should be available per strategy and setup.

---

# 13. Performance Analytics

The analytics engine is one of the most important components.

## Basic Metrics

* Total trades
* Winning trades
* Losing trades
* Win rate
* Average win
* Average loss
* Largest win
* Largest loss
* Gross profit
* Gross loss
* Net P&L
* Profit factor
* Expectancy
* Average R
* Median R
* Maximum drawdown

## Advanced Metrics

* R-multiple distribution
* Risk-adjusted return
* Sharpe ratio
* Sortino ratio
* Calmar ratio
* Recovery factor
* Maximum adverse excursion (MAE)
* Maximum favorable excursion (MFE)
* Average holding time
* Median holding time
* Consecutive wins
* Consecutive losses
* Payoff ratio
* Equity curve
* Drawdown curve

Metric definitions must be documented and consistent.

---

# 14. Performance Breakdown

Users must be able to analyze performance by:

* Strategy
* Setup
* Instrument
* Asset class
* Direction
* Long/short
* Day of week
* Time of day
* Trading session
* Month
* Quarter
* Year
* Market regime
* Account
* Tag
* Emotional state
* Discipline score
* Entry reason
* Exit reason

Example:

```text
Setup A
Trades: 146
Win Rate: 61%
Expectancy: +0.72R
Profit Factor: 1.94
Max Drawdown: 4.8%
```

Clicking a metric should allow drill-down to the underlying trades where practical.

---

# 15. P&L, Charges & Financial Calculation Engine

**Kubera — P&L Specialist** owns the financial calculation specification and validation.

All financial calculations must be deterministic and independently testable.

The calculation engine must support, where applicable:

* Realized P&L
* Unrealized P&L
* Gross P&L
* Net P&L
* Average entry price
* Average exit price
* Weighted average price
* Partial fills
* Partial exits
* Scale-in / scale-out
* Brokerage
* STT
* Exchange transaction charges
* GST
* SEBI charges
* Stamp duty
* Slippage
* Contract/lot-based calculations
* Futures MTM
* Options premium
* Multi-leg strategy P&L
* Corporate-action adjustments where supported

The system must preserve the distinction between:

```text
Execution Price
      ↓
Gross P&L
      ↓
Charges / Costs
      ↓
Slippage / Adjustments
      ↓
Net P&L
```

## Financial Calculation Rules

* AI must never be the source of financial truth.
* Monetary calculations must use appropriate decimal/precision handling.
* Rounding rules must be explicit.
* Currency handling must be explicit.
* Every calculation must be reproducible from authoritative source records.
* Calculation rules must be versioned when methodology changes.
* Financial calculations must have dedicated unit and integration tests.
* Reconciliation against broker statements must be supported.

# 15. Risk Management

The risk engine must calculate and monitor:

* Risk per trade
* Risk/reward
* Position size
* Account exposure
* Open risk
* Daily risk
* Weekly risk
* Portfolio risk
* Drawdown
* Daily loss
* Consecutive losses
* Strategy concentration
* Instrument concentration
* Correlated exposure

## Position Sizing

The system should support position-sizing calculations using configurable risk rules.

Example:

```text
Account Capital = ₹5,00,000
Risk % = 1%
Maximum Risk = ₹5,000

Entry = ₹250
Stop = ₹240

Risk/Share = ₹10

Position Size = 500 shares
```

The exact calculation must be deterministic and covered by unit tests.

---

# 16. Trading Psychology

The journal must capture behavioral information.

Possible fields:

* Emotional state
* Confidence
* Fear
* Greed
* FOMO
* Revenge trading
* Impatience
* Overconfidence
* Fatigue
* Stress
* Sleep quality
* Rule adherence
* Trading impulse

The system should analyze relationships between behavior and performance.

Example insight:

```text
FOMO Trades
Win Rate: 31%
Expectancy: -0.42R

Planned Trades
Win Rate: 58%
Expectancy: +0.76R
```

Insights must be based on sufficient sample sizes and should communicate uncertainty where appropriate.

---

# 17. Market Context

Users should be able to record or import contextual information such as:

* Market trend
* Volatility regime
* Index direction
* Sector performance
* News events
* Economic events
* Market session
* Market breadth
* VIX/volatility data where available

Future versions may automatically enrich trades with market context using external market-data providers.

---

# 18. Dashboard

The dashboard should provide a high-level view of the trader's performance.

## Required Dashboard Sections

### Account Overview

* Current equity
* Net P&L
* Daily P&L
* Weekly P&L
* Monthly P&L
* Drawdown

### Performance

* Win rate
* Expectancy
* Profit factor
* Average R
* Average win/loss

### Risk

* Current open risk
* Largest drawdown
* Daily risk utilization
* Risk violations

### Behavioral

* Rule adherence
* Most common mistakes
* Emotional performance patterns

### Recent Activity

* Recent trades
* Recent journal entries
* Alerts
* Import status

---

# 19. Advanced Charts

The product should support interactive charts including:

* Equity curve
* Drawdown curve
* P&L by day
* P&L distribution
* R distribution
* Win/loss distribution
* Monthly heatmap
* Calendar P&L
* Performance by setup
* Performance by instrument
* MAE/MFE scatter
* Risk/reward distribution
* Holding time distribution

Charts must support filtering and drill-down.

---

# 20. Trade Detail Page

Each trade should have a dedicated page.

Suggested layout:

```text
Trade Summary
│
├── Instrument / Direction
├── Entry / Exit
├── Quantity
├── P&L
├── R-Multiple
├── Risk
│
├── Trade Plan
│
├── Execution Timeline
│
├── Market Context
│
├── Screenshots
│
├── Psychology
│
├── Mistakes
│
├── Strategy / Setup
│
└── AI Analysis
```

---

# 21. AI Trading Assistant

AI must be positioned as an analytical layer over trusted trading data.

## AI capabilities

The assistant should be able to answer questions such as:

* What are my most profitable setups?
* What is my biggest recurring mistake?
* Which instruments am I most consistent on?
* How does my performance change after consecutive losses?
* What time of day performs best?
* How does my risk affect my drawdown?
* Which setups have negative expectancy?
* What changed in my trading performance this month?
* Which behavioral factors correlate with losses?

## AI should be able to generate

* Performance summaries
* Trade reviews
* Weekly reviews
* Monthly reviews
* Pattern explanations
* Rule-violation summaries
* Personalized improvement suggestions

## AI restrictions

AI must NOT:

* Alter authoritative trade records without explicit user action.
* Invent trading data.
* Invent financial calculations.
* Present statistically weak patterns as certainty.
* Execute trades.
* Give the impression that predictions are guaranteed.

AI responses must reference the underlying data/metrics used where practical.

---

# 22. Reports

Users should be able to generate:

* Daily trading report
* Weekly trading review
* Monthly performance report
* Strategy report
* Risk report
* Behavioral report
* Account statement summary

Export formats:

* CSV
* Excel
* PDF

Reports should support date/account/strategy filters.

---

# 23. Notifications & Alerts

The platform should support configurable alerts.

Examples:

* Daily loss limit exceeded
* Drawdown threshold exceeded
* Risk per trade exceeded
* Consecutive losses exceeded
* Rule violation
* High exposure
* Import failure
* Broker synchronization issue

Notifications may eventually support:

* In-app
* Email
* Push notifications

---

# 24. Search & Filtering

The product should provide powerful global filtering.

Filters should include:

* Date range
* Account
* Symbol
* Strategy
* Setup
* Direction
* Result
* P&L
* R-multiple
* Tags
* Emotion
* Mistake
* Market condition

Filters should be combinable.

Example:

```text
Strategy = Breakout
AND
Direction = Long
AND
Month = July
AND
Emotion = FOMO
AND
Result = Loss
```

---

# 25. Data Model

The architecture should separate raw and derived data.

Suggested conceptual entities:

```text
User
TradingAccount
Broker
Instrument
Order
Execution
Position
Trade
JournalEntry
Strategy
Setup
Tag
TradeTag
MarketContext
PsychologyEntry
RiskEvent
PortfolioSnapshot
PerformanceSnapshot
ImportJob
ImportRecord
Attachment
Notification
AuditLog
AIInsight
```

Relationships must be explicitly designed before implementation.

---

# 26. Data Integrity

The system must maintain:

* Immutable raw execution records where appropriate
* Idempotent imports
* Duplicate detection
* Referential integrity
* Audit history
* Import logs
* Calculation reproducibility
* Data validation

Every derived value should be reproducible from authoritative source data.

---

# 27. Database Requirements

The database must support:

* Multiple users
* Multiple accounts per user
* Multiple brokers per user
* Large trade histories
* Efficient time-series queries
* Aggregated analytics
* Indexing for common filters
* Transactional integrity

The schema must be designed for future scale.

PostgreSQL is the preferred initial relational database unless architecture review identifies a strong reason otherwise.

---

# 28. Backend Requirements

The backend should expose a versioned API.

Expected API domains:

```text
/auth
/users
/accounts
/brokers
/instruments
/orders
/executions
/positions
/trades
/journal
/strategies
/setups
/analytics
/risk
/psychology
/imports
/reports
/ai
/notifications
/admin
```

The backend must implement:

* Authentication
* Authorization
* Validation
* Business logic
* Calculation engines
* Import processing
* Analytics
* API error handling
* Logging
* Auditing

Financial business logic must remain outside the presentation layer.

---

# 29. Frontend Requirements

The UI should be:

* Responsive
* Fast
* Accessible
* Data-dense without becoming confusing
* Designed for frequent daily use

Primary screens:

1. Login
2. Dashboard
3. Trade Journal
4. Trade Detail
5. Add Trade
6. Import Trades
7. Strategies
8. Analytics
9. Risk
10. Psychology
11. Reports
12. AI Assistant
13. Settings
14. Account/Broker Management

---

# 30. Performance Requirements

The application should:

* Load major dashboard views quickly.
* Paginate large trade lists.
* Avoid loading unnecessary historical records.
* Cache expensive aggregations where appropriate.
* Process large imports asynchronously.
* Provide import progress.
* Avoid blocking normal UI operations during analytics generation.

Performance targets should be finalized during technical design and load testing.

---

# 31. Security Requirements

The security layer must address:

* Authentication
* Authorization
* Input validation
* SQL injection prevention
* XSS prevention
* CSRF protection where applicable
* Rate limiting
* Secure cookies/tokens
* Secret management
* Encryption of sensitive credentials
* Secure file uploads
* Malware/content validation for attachments where appropriate
* Audit logging
* Dependency/security scanning

Broker credentials and API keys are highly sensitive and must receive special protection.

---

# 32. DevOps & Deployment

The application should have separate environments:

```text
Development
     ↓
Test / QA
     ↓
UAT / Staging
     ↓
Production
```

CI/CD should include:

* Linting
* Unit tests
* Integration tests
* API tests
* Frontend tests
* Security checks
* Build verification
* Deployment

Production deployments must support rollback.

---

# 33. Testing Strategy

Testing must exist at multiple levels.

## Unit Testing

Especially for:

* P&L calculations
* Fees
* Position sizing
* R-multiple
* Drawdown
* Trade reconstruction
* Metric calculations

## Integration Testing

Test:

* Database
* API
* Import pipeline
* Broker adapters
* Authentication

## End-to-End Testing

Test critical user journeys:

```text
Login
→ Create account
→ Import trades
→ Reconstruct trades
→ Journal trade
→ View analytics
→ Generate report
```

## Data Testing

Test malformed, duplicated, incomplete, and inconsistent broker files.

---

# 34. Observability

The system must provide:

* Structured application logs
* Error tracking
* API metrics
* Import-job monitoring
* Database monitoring
* Performance monitoring
* Health checks
* Audit logs

Critical failures should be observable and actionable.

---

# 35. Admin Panel

Administrators should be able to:

* Manage users
* View system health
* View import failures
* View broker integration status
* Manage supported brokers
* Manage instruments/reference data
* View audit logs
* Manage feature flags
* Manage system configuration

Administrative privileges must be tightly controlled.

---

# 36. Non-Functional Requirements

The product should be:

* Secure
* Reliable
* Maintainable
* Testable
* Observable
* Scalable
* Modular
* Extensible
* Deterministic for financial calculations

The system should minimize vendor lock-in where practical.

---

# 37. Important Architectural Rule

The product must use this conceptual hierarchy:

```text
RAW DATA
   ↓
VALIDATED DATA
   ↓
TRADING DOMAIN MODEL
   ↓
DETERMINISTIC CALCULATIONS
   ↓
ANALYTICS
   ↓
AI INTERPRETATION
```

Not:

```text
RAW DATA
   ↓
AI
   ↓
Financial Numbers
```

AI is an interpretation and intelligence layer, not the accounting engine.

---

# 38. Initial MVP

The first implementation should not attempt every advanced feature.

## MVP Scope

### Phase 1

* Authentication
* User/account management
* Manual trade entry
* CSV import
* Instruments
* Orders/executions
* Basic trade reconstruction
* Journal
* Basic P&L
* Basic dashboard
* Basic analytics
* Strategy/setup tagging
* Basic risk metrics
* QA infrastructure
* CI/CD

### Phase 2

* Broker integrations
* Advanced analytics
* Advanced risk
* Psychology module
* Interactive reports
* Market context
* Advanced charts

### Phase 3

* AI trading assistant
* Behavioral intelligence
* Automated insights
* Advanced statistical analysis
* Monte Carlo analysis
* Personalized coaching
* Additional brokers
* Mobile application

---

# 39. Definition of Done

A feature is complete only when:

* Requirements are clear.
* Product acceptance criteria exist.
* Architecture is approved where applicable.
* Implementation is complete.
* Unit tests are added.
* Integration/E2E tests are added where relevant.
* Security implications are reviewed.
* UI/UX is reviewed.
* Documentation is updated.
* Error handling is implemented.
* Logging/observability is adequate.
* QA has validated the feature.
* No known critical defects remain.

---

# 40. Agent Responsibilities

## Krishna — Project Manager

Owns:

* Roadmap execution
* Planning
* Scope coordination
* Milestones
* Task assignment
* Dependencies
* Delivery tracking
* Blockers
* Sprint/release coordination
* Cross-agent coordination
* Definition of Done enforcement
* Delivery risk management

Krishna coordinates the team but does not replace the domain authority of Product, Architecture, Quant, Risk, P&L, Security, or QA.

## Yudhishthira — Product Manager

Owns:

* Product requirements
* User stories
* Acceptance criteria
* Product roadmap
* Feature prioritization
* User outcomes
* Product discovery
* Product metrics / OKRs

## Usha — UI/UX Designer

Owns:

* User flows
* Information architecture
* Wireframes
* Design system
* Interaction design
* Accessibility
* Usability testing
* Visual consistency

## Mayasura — Software Architect

Owns:

* System architecture
* Domain architecture
* Technology decisions
* Service/module boundaries
* Scalability
* Data architecture
* API architecture
* ADRs
* Technical standards

## Arjuna — Senior Frontend Engineer

Owns:

* React/TypeScript frontend
* State management
* API integration
* Interactive charts
* Frontend performance
* Accessibility implementation
* Component architecture

## Bhima — Senior Backend Engineer

Owns:

* Backend APIs
* Business/domain services
* Authentication and authorization implementation
* Validation
* Async/background processing
* Database access
* Backend observability

## Nakula — Senior DevOps / SRE Engineer

Owns:

* Infrastructure
* CI/CD
* Cloud deployment
* Infrastructure as Code
* Kubernetes where justified
* Monitoring
* Logging
* Reliability
* Backups and recovery

## Hanuman — Senior Security Engineer

Owns:

* Threat modeling
* Application security
* Penetration-testing strategy
* Secure coding review
* Secrets management
* Authentication security
* Vulnerability management
* Security gates

## Sahadeva — QA Engineer

Owns:

* Test strategy
* Test automation
* Regression testing
* End-to-end testing
* Defect management
* Quality gates
* Release validation
* Test-data strategy

## Vishwakarma — ML/AI Engineer

Owns:

* LLM integrations
* AI assistant
* RAG/context pipelines
* Agent workflows
* ML pipelines
* Model evaluation
* AI guardrails
* AI observability

## Vyasa — Data Engineer

Owns:

* Data pipelines
* ETL/ELT
* dbt/data transformations
* Time-series data
* Broker ingestion
* Data normalization
* Data quality pipelines
* Data orchestration

## Narada — Data Scientist

Owns:

* Statistical modeling
* Experimentation
* Causal/statistical analysis
* Pattern discovery
* Model validation
* Statistical uncertainty analysis

## Chitragupta — Data Analyst

Owns:

* SQL analytics
* Dashboards
* Reporting metrics
* Exploratory analysis
* A/B analysis where applicable
* Data storytelling
* Product analytics

## Karna — Quant Researcher

Owns:

* Trading-performance methodology
* Win-rate analysis
* Expectancy
* R-multiples
* Risk-adjusted metrics
* Monte Carlo analysis
* Sharpe/Sortino methodology
* Quantitative research

## Ganesha — Trading Domain Analyst

Owns:

* Trading-domain requirements
* Trade lifecycle semantics
* Instrument and order concepts
* Options/multi-leg concepts
* Strategy/setup semantics
* Trading data model requirements
* Broker-domain normalization rules

## Sanjaya — Broker Integration Engineer

Owns:

* Broker APIs
* Broker CSV imports
* Authentication flows for broker connections
* Synchronization
* Reconciliation
* Rate-limit handling
* Broker-specific adapters
* Market-data integration boundaries

## Dhanvantari — Risk Management Engineer

Owns:

* Position sizing
* Risk-per-trade
* Risk/reward
* Portfolio exposure
* Drawdown
* Risk tiers
* Risk alerts
* Risk-of-ruin analysis
* Risk rules and validation

## Vidura — Trading Psychology Analyst

Owns:

* Trading psychology model
* Behavioral taxonomy
* FOMO/revenge/impulse tracking
* Rule adherence
* Discipline scoring
* Behavioral-performance analysis
* Behavioral insights

## Kubera — P&L Specialist

Owns:

* P&L calculation methodology
* Brokerage and charge calculations
* STT and applicable statutory charges
* Slippage treatment
* MTM
* Average entry/exit calculations
* Corporate-action treatment where applicable
* Financial reconciliation
* Financial calculation test cases

## Drona — Learning & Growth

Drona is a global support skill rather than a core production implementation owner.

For this project, Drona may be used for:

* Learning unfamiliar technologies
* Explaining architecture concepts
* Creating study plans
* Developer upskilling
* Interview/career preparation
* Documentation of learning material

Drona must not override project, product, architecture, financial, or security decisions.

# 41. Collaboration Rules

Agents must not silently overwrite decisions owned by another role.

When disagreement occurs:

```text
Project delivery / priority / dependency
→ Krishna

Product / user requirement
→ Yudhishthira

UI / UX
→ Usha

Technical architecture
→ Mayasura

Trading-domain semantics
→ Ganesha

P&L / financial calculation
→ Kubera

Quant methodology / statistical performance
→ Karna

Risk methodology
→ Dhanvantari

Broker / market integration
→ Sanjaya

Trading psychology
→ Vidura

Data pipelines / data quality
→ Vyasa

Analytics / reporting
→ Chitragupta

Data science / experimentation
→ Narada

AI / ML
→ Vishwakarma

Frontend implementation
→ Arjuna

Backend implementation
→ Bhima

Infrastructure / delivery platform
→ Nakula

Security
→ Hanuman

Quality / release gates
→ Sahadeva

Learning / technology education
→ Drona
```

Cross-functional decisions must be documented when they materially affect architecture, financial correctness, data contracts, security, or product behavior.

# 42. Source-of-Truth Hierarchy

The project must maintain explicit ownership boundaries.

```text
Product Requirements
        ↓
Yudhishthira

Project Delivery / Coordination
        ↓
Krishna

Technical Architecture
        ↓
Mayasura

Trading Domain Rules
        ↓
Ganesha

P&L / Financial Calculation Rules
        ↓
Kubera

Quantitative Methodology
        ↓
Karna

Risk Methodology
        ↓
Dhanvantari

Behavioral Methodology
        ↓
Vidura

Validated Trading Data
        ↓
Database / Data Layer

Derived Analytics
        ↓
Chitragupta / Narada / Karna

AI Interpretation
        ↓
Vishwakarma
```

AI-generated insights remain derived interpretations. They must never silently become authoritative financial or trading records.

# 43. Future Expansion

The architecture should leave room for:

* Mobile apps
* Wearables/notifications
* Advanced market-data integrations
* Automated strategy tagging
* Screenshot/chart analysis
* AI trade grading
* Personalized trading coach
* Team accounts
* Coach/client accounts
* Social/community features
* Strategy backtesting
* Trading plan enforcement
* Broker auto-sync
* Real-time risk monitoring
* API for third-party applications

---

# 44. Success Criteria

The product should ultimately enable a trader to answer:

### "What happened?"

* How much did I make/lose?
* What trades did I take?
* What happened today/week/month?

### "Why did it happen?"

* Which setups worked?
* Which conditions hurt performance?
* What mistakes did I make?
* Did my risk management change?

### "What should I change?"

* Which behaviors should I eliminate?
* Which setups should I focus on?
* Where am I taking excessive risk?
* What patterns consistently improve my expectancy?

### "Am I improving?"

* Is expectancy improving?
* Is drawdown decreasing?
* Is discipline improving?
* Are rule violations decreasing?
* Is my process becoming more consistent?

That is the ultimate purpose of the product.

---

# 45. Initial Engineering Order

Implementation should proceed in this general sequence:

```text
1. Product requirements
        ↓
2. Domain model
        ↓
3. System architecture
        ↓
4. Database schema
        ↓
5. Backend foundation
        ↓
6. Authentication/account management
        ↓
7. Order/execution model
        ↓
8. Trade reconstruction engine
        ↓
9. Journal
        ↓
10. Deterministic P&L engine
        ↓
11. Deterministic risk engine
        ↓
12. Frontend foundation
        ↓
13. Dashboard
        ↓
14. Analytics
        ↓
15. Import system
        ↓
16. QA hardening
        ↓
17. Deployment
        ↓
18. Broker integrations
        ↓
19. Advanced analytics / psychology
        ↓
20. AI layer
```

The sequence may be adjusted by Krishna and Mayasura when technical dependencies require it.
