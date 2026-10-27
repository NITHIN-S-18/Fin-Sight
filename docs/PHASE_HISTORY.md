# PHASE_HISTORY.md

# FinSight Development History

## Phase 3 Trial and Authorization Intelligence

Status

✅ Completed

Completed

- Added tenant-scoped persistent authorization and trial-intelligence records.
- Added explicit authorization, possible-trial, possible-conversion, and
  confirmed-recurring states with preserved evidence.
- Reconciled records by stable uploaded transaction identity to prevent
  duplicate alerts across repeated CSV uploads.
- Added authenticated `GET /trial-intelligence` and detail access.
- Added optional Resend delivery configuration with safe failure handling.
- Integrated a small informational alert section into Commitments without
  changing exposure, health, ML, or recurring-payment semantics.

Conversion dates are only derived from explicit trial-duration wording.
Unknown dates remain unavailable and do not produce countdowns or scheduled
emails.

This document tracks the complete implementation history of FinSight.

Every completed phase is considered verified and frozen unless explicitly reopened.

## Model 4 financial shortfall prediction

Status

✅ ML accepted pending ongoing runtime monitoring

Completed

- Added observed next-calendar-month shortfall labels from successful positive
  transaction cash flow only; no Model 1 or predicted values define the target.
- Added leakage-safe historical income, commitment, variable-spend, cash-buffer,
  payment-reliability, recurring-commitment, and Model 1 forecast features.
- Added an independently defined deterministic baseline and chronological plus
  user-disjoint evaluation.
- Persisted `financial_shortfall/v1.0` with train-only preprocessing and a
  reloadable `HistGradientBoostingClassifier` artifact.
- Added authenticated, tenant-scoped `GET /api/v1/ml/shortfall/{user_id}` with
  categorical risk output, insufficient-history handling, and deterministic
  artifact fallback.

Evidence

- 3,444 observed monthly snapshots from 241 users and 11,365 transactions.
- Validation balanced accuracy: ML `0.8701`, baseline `0.7861`.
- Untouched temporal test balanced accuracy: ML `0.8957`, baseline `0.7873`.
- Unseen-user balanced accuracy: ML `0.7105`; user intersections are all zero.
- Focused Model 4 tests: `6 passed`.

## Phase 14 Model 2 financial goal feasibility

Status

✅ Baseline implementation completed; supervised ML not accepted

Completed

- Added authenticated Model 2 feasibility and tenant-scoped goal CRUD APIs.
- Reused the frozen Model 1 cash-flow forecast as the source of expected
  income, committed expenses, variable expenses, and net cash.
- Added observed-history category flexibility adjustments without changing
  commitments or protected categories.
- Added persistent financial goals and migration `014_create_financial_goals`.
- Explicitly withheld fabricated labels, probabilities, and ML production
  claims because the available data lacks an independent observed goal outcome.

Verification

- `python -m compileall app`
- `git diff --check`

## Phase 5B Cash-flow model training foundation

- Added leakage-safe `CashFlowModelTrainer` with separate
  `HistGradientBoostingRegressor` models for income, committed expenses, and
  variable expenses.
- Added chronological split metadata, train-only preprocessing, deterministic
  seeds, persistence/reload, and non-negative component inference.
- Extended forecast response metadata with model type/version and data cutoff
  while preserving baseline authority until production acceptance.

## Final ML Quality and Dataset Audit

Status

✅ Completed

Completed

- Preserved the existing reference dataset and temporal T → T+1 formulation.
- Removed the static full-ledger capacity fallback from temporal snapshots to
  prevent future-information leakage.
- Added dataset metadata for date range, status distribution, duplicates,
  snapshot coverage, and exposure-target availability.
- Added chronological split metadata for user counts and train/validation/test
  target class summaries.
- Added classification confusion matrices, class counts, and positive rates to
  persisted evaluation reports.
- Replaced the unconditional K=5 behaviour choice with candidate evaluation,
  silhouette-based selection, and a deterministic tie preference for K=5.
- Added regression coverage for future-value mutation leakage and unavailable
  future exposure targets.

Verification

- `python -m compileall app`
- Focused ML quality regression tests
- Reference temporal-data smoke probe

## Model 1 unseen-user generalization audit

Status

✅ Completed

Completed

- Added a deterministic user-disjoint evaluation with 3,500 development,
  750 validation, and 750 unseen-test users.
- Confirmed that preprocessing and model fitting use development users only,
  selection uses validation users only, and no user IDs overlap.
- Added unseen-user metrics, predeclared generalization classifications,
  representative case studies including the largest-error case, and
  non-negative/derived-output sanity checks.
- Confirmed the accepted production artifact remains unchanged.

The audit supports strong unseen-user generalization for variable-expense
HistGradientBoosting (6.14% improvement over its strongest unseen-user
baseline). Income and committed-expense predictions retain deterministic
baselines and show no meaningful additional model generalization benefit.

Verification

- `python -m compileall app`
- Unseen-user evaluation runner
- Unseen-user regression assertions

---

## Phase 15 Global Dataset Authorization

Status

✅ Completed

Completed

- Confirmed that the global `/dataset/users`, `/dataset/transactions`, and
  `/dataset/summary` routes exposed reference and aggregate financial data to
  any authenticated account without tenant authorization.
- Verified that no frontend code uses these global routes.
- Removed the global routes from the user-facing API.
- Preserved scoped dataset routes, which continue to require the JWT-linked
  financial user and reject cross-account access with `403`.
- Updated smoke coverage and API documentation to prevent regression.

Verification

- `python -m compileall app`
- Targeted dataset and isolation tests
- Complete backend suite

---

## Phase 13 Complete Backend Testing

Status

✅ Completed

Completed

- Added an end-to-end two-user regression flow covering registration, login,
  authenticated account lookup, empty dashboard and transaction states, CSV
  upload, import history, dashboard, transactions, subscriptions, EMI, BNPL,
  exposure and financial health, ML intelligence, Copilot, and What-If
  simulation.
- Verified that each account receives only its own uploaded transaction and
  commitment data.
- Verified empty accounts receive explicit unavailable-data responses for
  exposure, ML, Copilot, and What-If operations.
- Verified authenticated cross-account requests are rejected with `403`.

Verification

- `python -m compileall app`
- Complete flow test: `1 passed`
- Full backend suite: `60 passed, 0 failed, 0 skipped, 0 errors`

---

## Phase 12 Error Handling and API Quality

Status

✅ Completed

Completed

- Standardized HTTP error responses while preserving status codes and
  structured validation details.
- Malformed JSON request bodies now return `400`; schema and CSV validation
  failures return `422`.
- Added safe centralized handling for SQLAlchemy database failures with
  server-side logging and generic client messages.
- Centralized unexpected-error logging without exposing exception text,
  credentials, tokens, or database details.
- Removed Copilot endpoint-level broad exception wrappers so programming and
  backend failures reach the centralized error boundary.
- Preserved explicit `401`, `403`, `404`, and `409` behavior.
- Confirmed ML and Copilot failures do not return fabricated predictions or
  financial metrics.
- Added status-code and error-sanitization regression tests.

Verification

- `python -m compileall app`
- Phase 12 targeted tests: `16 passed`
- Full backend suite: `59 passed`

---

## Phase 11 Performance Optimization

Status

✅ Completed

Measured baseline bottlenecks:

- Dashboard: approximately 225 ms median and 42 SQL statements.
- Exposure: approximately 134 ms median and 22 SQL statements.
- Copilot: approximately 141 ms median and 24 SQL statements.
- Login was approximately 109 ms median and model-bound rather than a
  repeated-dataset bottleneck.

Completed

- Added a request-scoped DatasetService cache for repeated authenticated user
  and transaction reads.
- Reused cached dataset results across dashboard, commitment, exposure, ML,
  and Copilot orchestration within one request.
- Kept the cache isolated per request to prevent stale data and cross-account
  leakage.
- Preserved upload invalidation and all financial calculations.

Measured after optimization:

- Dashboard: approximately 159 ms median and 5 SQL statements.
- Exposure: approximately 112 ms median and 5 SQL statements.
- Copilot: approximately 90 ms median and 7 SQL statements.
- ML intelligence: approximately 146 ms median and 5 SQL statements.
- Login: approximately 134 ms median and 1 SQL statement.

Verification

- `python -m compileall app`
- Full backend suite: `57 passed`

---

## Phase 10 Copilot Backend Refinement

Status

✅ Completed

Completed

- Copilot financial snapshots now come exclusively from the authenticated
  user's ExposureService data.
- Removed fabricated fallback income, commitments, health, and commitment
  records from production Copilot execution.
- Exposure and domain errors are no longer swallowed by the Copilot snapshot
  builder or endpoint boundary.
- Scenario parameters are copied before inference so request-owned input is
  not mutated.
- Added regression tests for authoritative context, backend failure
  propagation, missing dependencies, and scenario immutability.

Verification

- `57 passed`

---

## Phase 6 ML Quality Improvement

Status

✅ Completed

Objective

Improve the quality, evaluation, and explainability of the existing Random
Forest, K-Means, and Isolation Forest models without changing algorithms.

Completed

- Preprocessing now splits raw rows before fitting imputation and scaling state.
- Random Forest metadata identifies distress and exposure supervision as synthetic
  rule-derived targets.
- K-Means validation now persists silhouette evaluation and candidate cluster
  comparisons for K=2 through K=8 where supported.
- Isolation Forest metadata records contamination, decision threshold, score
  semantics, validation alert rate, and score range.
- CSV reference mode no longer attempts to query PostgreSQL for reference users
  and transactions during ML feature construction.
- Added regression tests for leakage prevention, cluster evaluation, and anomaly
  score interpretation.

Decision

- Random Forest: keep the algorithm and improve training data/evaluation.
- K-Means: keep the algorithm and improve cluster validation.
- Isolation Forest: keep the algorithm and improve threshold/evaluation
  documentation.

Verification

- Compilation
- ML quality regression tests
- CSV ML bootstrap and artifact metadata validation

Frozen

✅ Yes

---

## Phase 7 Intelligence + Recommendations

Status

✅ Completed

Objective

Validate fused predictive intelligence against authenticated user data and
improve explanation, recommendation, and confidence correctness.

Completed

- Empty financial accounts are rejected before model inference, preventing
  fabricated intelligence from zero-valued feature rows.
- Fusion validates engine identifiers, duplicate outputs, finite confidence
  values, and confidence bounds.
- Fusion records weighted confidence contributions and its aggregation basis.
- Anomaly explanations now use the model decision score rather than the boolean
  anomaly flag.
- Distress recommendations reference only commitment pressures present in the
  user's metrics.
- Added fusion, empty-account, confidence, and explanation regression tests.

Verification

- Compilation
- Phase 7 intelligence tests
- Phase 6 ML regression tests
- API documentation update

Frozen

✅ Yes

---

## Phase 8 What-If / Digital Twin API

Status

✅ Completed

Objective

Expose the existing Digital Twin, Scenario Builder, and Comparison Engine
through an authenticated, non-persistent simulation endpoint.

Completed

- Added `POST /api/v1/simulator/simulate`.
- Baseline state is derived from the JWT-linked account through ExposureService.
- Scenario parameters do not accept or override a user ID.
- Existing Digital Twin and Scenario Builder logic is reused unchanged.
- Simulation output is compared using the existing Comparison Engine.
- Simulations remain in memory and do not modify transactions or financial
  records.
- Added tests for twin isolation, authenticated baseline mapping, deltas, and
  unsupported scenarios.

Verification

- Compilation
- Simulator unit/service tests
- API documentation update

Frozen

✅ Yes

---

## Phase 9 Historical Data + Dashboard Graph API

Status

✅ Completed

Objective

Provide an authenticated monthly time series derived only from the user's
stored transaction history.

Completed

- Added `GET /api/v1/dashboard/history`.
- Aggregates successful income, spending, and commitment transactions by
  observed calendar month.
- Calculates exposure and available capacity only when monthly income exists.
- Returns a clearly identified transaction-only financial health approximation.
- Does not fabricate missing months, profile values, or reference-user data.
- Added multi-month aggregation and empty-history tests.

Verification

- Compilation
- Historical service tests
- Full backend suite
- API documentation update

Frozen

✅ Yes

## Authentication

Status

Implemented

Completed

- Separate `auth_users` account table
- Password hashing with scrypt
- JWT registration, login, and current-user endpoints
- Authentication endpoint tests

Verification

- Compilation
- Migration validation
- Authentication endpoint tests

---

## Phase 7

Status

✅ Completed

Objective

Dashboard Intelligence

Completed

- Unified dashboard orchestration
- Dashboard response models
- Frontend-friendly aggregation

Verification

- Compile
- Swagger
- HTTP tests
- Cross-service validation

Frozen

✅ Yes

---

## Phase 8

Status

✅ Completed

Objective

ML Infrastructure & Data Engineering

Completed

- ML package foundation
- Feature engineering pipeline
- Preprocessing framework
- Generic training framework
- Evaluation utilities
- Inference utilities
- Model persistence

Verification

- Compile

Frozen

✅ Yes

---

## Phase 9

Status

✅ Completed

Objective

Future Prediction Models

Completed

- Financial Distress Engine
- Exposure Forecast Engine
- Behaviour Intelligence Engine
- Financial Anomaly Engine
- Financial Intelligence Fusion Layer
- AI Insights Layer
- Predictive Intelligence API endpoints

Verification

- Compile
- Model persistence
- Inference
- Fusion layer
- API endpoints
- Swagger

Frozen

✅ Yes

---

## Phase 10 – Wave 1

Status

✅ Completed (Wave 1)

Objective

AI Financial Decision Copilot - Financial Digital Twin Infrastructure

Completed

- Intent Engine (IntentDetector with 8 supported financial intent types & keyword matching)
- Intent Router (IntentRouter mapping intents to internal engines without execution)
- Digital Twin Engine (DigitalTwinEngine with FinancialSnapshot, TwinMetadata, DigitalTwin, isolated cloning, validation, and no persistence)
- Scenario Builder (ScenarioBuilder supporting all 8 financial change scenarios)
- Comparison Engine (ComparisonEngine calculating exact metrics deltas between snapshots)

Verification

- Compile (python -m compileall app)
- Unit & Smoke Tests for all 5 Wave 1 modules
- Zero circular imports, zero external dependencies

Frozen

✅ Yes (Wave 1 Infrastructure)

---

## Phase 10 – Wave 2

Status

✅ Completed (Wave 2)

Objective

Decision Intelligence & Behavioral Fingerprinting Infrastructure

Completed

- Decision Engine (DecisionEngine orchestrating Business Rules, ML, Digital Twin & XAI to produce a unified recommendation)
- Decision Confidence Engine (DecisionConfidenceEngine deterministically evaluating recommendation trustworthiness)
- Financial DNA Engine (DNAEngine deriving 7 behavioral traits and primary financial archetype from financial snapshot intelligence)

Verification

- Compile (python -m compileall app)
- Import and integration smoke tests for DecisionEngine, DecisionConfidenceEngine, and DNAEngine
- Zero circular imports, zero external dependencies

Frozen

✅ Yes (Wave 2 Intelligence)

---

## Phase 10 – Wave 3

Status

✅ Completed (Wave 3)

Objective

Experience Layer Infrastructure

Completed

- Opportunity Engine (OpportunityEngine generating proactive financial opportunities from Decision Engine & DNA)
- Timeline Engine (TimelineEngine constructing historical, current, future, and alternative branch events)
- Goals Engine (GoalsEngine evaluating goal progress, monthly savings requirements, and affordability)
- Replay Engine (ReplayEngine comparing expected simulation outputs vs actual snapshot metrics to calculate accuracy)

Verification

- Compile (python -m compileall app)
- Import and integration smoke tests for OpportunityEngine, TimelineEngine, GoalsEngine, and ReplayEngine
- Zero circular imports, zero external dependencies

Frozen

✅ Yes (Wave 3 Experience Layer)

---

## Phase 10 – Wave 4

Status

✅ Completed (Wave 4)

Objective

AI Financial Decision Copilot Service & REST API Orchestration Layer

Completed

- Copilot Service (CopilotService orchestrating Intent Detector, Intent Router, Digital Twin, Decision Engine, DNA, and Experience Layer)
- Response Generator (ResponseGenerator producing deterministic, natural language decision intelligence output without LLMs)
- Copilot Schemas (CopilotQueryRequest, CopilotResponse, CopilotOpportunityItem, CopilotSuggestionsResponse)
- Copilot REST APIs (POST /api/v1/copilot/query, GET /api/v1/copilot/suggestions/{user_id})

Verification

- Compile (python -m compileall app)
- Standalone service integration smoke tests
- FastAPI REST API endpoint smoke tests
- Swagger schema & route registration

Frozen

✅ Yes (Phase 10 Copilot Backend Complete & Frozen)

---

## Phase 11

Status

⏳ Pending

Objective

Deployment and Testing
- Project Structure
- Versioned APIs
- Configuration
- Logging
- Middleware
- Exception Framework

Verification

✅ Passed

Frozen

✅ Yes

---

## Phase 2

Status

✅ Completed

Objective

Dataset Intelligence

Completed

- DatasetService
- Dataset Summary
- User Profile
- Financial Profile
- CSV Processing
- Dataset APIs

Verification

✅ Passed

Frozen

✅ Yes

---

## Phase 3

Status

✅ Completed

Objective

Subscription Intelligence

Completed

- Subscription Detection
- AutoPay Detection
- Trial Detection
- Active Subscription Analytics
- Subscription Insights
- Subscription Summary
- Recommendation Rules

Verification

- Swagger
- HTTP Tests
- Smoke Tests
- Business Rule Validation

Status

Verified

Frozen

✅ Yes

---

## Phase 4

Status

✅ Completed

Objective

EMI Intelligence

Completed

- Active EMI Detection
- Loan Classification
- EMI Summary
- Payment Analytics
- Financial Analytics
- EMI Insights

Verification

- Compile
- Swagger
- HTTP Tests
- Manual Verification

Frozen

✅ Yes

---

## Phase 5

Status

✅ Completed

Objective

BNPL Intelligence

Completed

- Provider Detection
- Installment Detection
- Payment Analytics
- Financial Analytics
- BNPL Insights
- Provider Concentration Rules

Verification

- Compile
- Swagger
- Smoke Tests
- Business Rule Validation

Frozen

✅ Yes

---

## Phase 6

Status

✅ Completed

Objective

Financial Exposure Engine

Completed

- Exposure Score
- Financial Health
- Recommendation Engine
- Forecast Engine
- Explainability
- Financial Flexibility
- Available Capacity
- Recommendation Prioritization

Verification

- Compile
- Swagger
- HTTP Tests
- Cross-Service Validation
- Business Rule Validation

Frozen

✅ Yes

---

# Current Status

Current Stable Version

Backend v1.0

Implemented Modules

✅ Dataset

✅ Subscription

✅ EMI

✅ BNPL

✅ Exposure

Project Stability

Production Ready Backend

---

# Upcoming Phases

## Phase 7

Dashboard Intelligence

Status

⏳ Pending

---

## Phase 8

Frontend Dashboard

Status

⏳ Pending

---

## Phase 9

Authentication (Optional)

Status

⏳ Pending

---

## Phase 10

Deployment

Status

⏳ Pending

---

## Phase 11

Testing & Documentation

Status

⏳ Pending

---

# Development Policy

Completed phases should remain frozen.

Future work should extend existing modules rather than redesigning them.

## Task 5B Gemini Copilot Provider

Status

✅ Completed

Completed

- Added Gemini as the primary optional Copilot explanation provider using the
  official `google-genai` client and `GEMINI_MODEL`.
- Added bounded provider calls and a fallback chain of Gemini, local Ollama,
  then the existing deterministic response generator.
- Kept all financial metrics, ML outputs, scenarios, and recommendations
  authoritative in existing backend services.
- Restricted provider context to a compact authenticated-user financial
  snapshot and structured decision factors.
- Added mocked provider regression coverage without making real Gemini calls.

Verification

- Focused Copilot/provider tests
- Full backend suite
- Frontend production build
- Backend compilation
- `git diff --check`

Major architectural changes require explicit approval.

Every phase must end with

- Compile Success
- Swagger Verification
- HTTP Verification
- Smoke Tests
- Business Rule Validation
- Documentation Update

---

# Release History

Backend v1.0

Status

Stable

Includes

- Dataset Intelligence
- Subscription Intelligence
- EMI Intelligence
- BNPL Intelligence
- Exposure Engine

Ready for Dashboard Integration.
## Phase 4 - Unified Commitment Engine

Implemented the canonical current commitment snapshot over persisted recurring
payments. Active `USER_ADDED` records and active high-confidence `DETECTED`
records are included using the existing monthly normalization rules. Low
confidence, inactive, trial/authorization-only, negative, and duplicate
transaction evidence do not create authoritative commitment burden. The
authenticated `/api/v1/commitments` endpoint and Commitments page now consume
the canonical total, while existing Subscription, EMI, BNPL, history, and
trial-alert contracts remain available.

## Phase 5 - Next-month cash-flow forecasting

Added a leakage-safe cash-flow forecast layer for authenticated users. Monthly
income, committed expenses, and variable expenses are built from observed
successful positive transactions only; target month values are never used as
features. The forecast requires six months of observed history, uses
chronological train/validation/test metadata, compares previous-month and
rolling-average baselines, and derives total expenses and net cash from the
component forecasts. Short histories are reported as unavailable rather than
fabricated.

## Model 2 Phase B observed-outcome ML evaluation

Status

✅ Completed; ML accepted with deterministic arithmetic retained

Completed

- Added leakage-audited historical goal scenarios from the 5,000-user
  longitudinal reference dataset.
- Used six contiguous history months and six contiguous future months.
- Constructed labels exclusively from actual successful future income,
  variable spending, and the pre-goal historical committed-expense mean;
  commitment reductions cannot create a positive label, and Model 1
  predictions are not used for labels.
- Added deterministic conservative, moderate, and ambitious savings tiers
  derived from historical buffer quantiles.
- Added chronological and user-disjoint split metadata, class-balance checks,
  overlap counts, and unseen-user evaluation.
- Evaluated HistGradientBoostingClassifier. XGBoost was skipped because it is
  not installed in the backend environment.

Decision

- 195,000 scenarios were generated for 5,000 users.
- Feasible labels: 38,302; infeasible labels: 156,698.
- Validation balanced accuracy: baseline `0.5968`, ML `0.6848`.
- Final temporal-test balanced accuracy: `0.6992`.
- Unseen-user balanced accuracy: `0.6491`.
- ML passed the predeclared acceptance gate and
  `model-2-phase-b-v1.pkl` was persisted.
- The authenticated goal API uses the accepted model as its feasibility
  decision signal. Model 1 values and all arithmetic remain deterministic;
  no probability is exposed.

Verification

- `python -m compileall backend/app backend/scripts/train_goal_feasibility.py`
- Phase B scenario and label smoke checks
- `git diff --check`
- `goal_feasibility_final_evaluation_report.json` generated

## Model 2 Phase C train/serve contract correction

Status

✅ Completed

Completed

- Added explicit `goal_amount`, `timeframe_months`, and
  `required_monthly_saving` to every generated scenario.
- Mapped the historical savings tiers deterministically to 12, 6, and 3
  month horizons and calculate `goal_amount` as required saving multiplied by
  timeframe.
- Preserved the observed-future label definition and six-month future window.
- Added confusion matrices, baseline unseen-user metrics, scenario
  distributions, artifact metadata, and the predeclared generalization rubric
  to the evaluation report.
- Persisted the accepted versioned artifact
  `model-2-phase-c-v2.pkl` and updated live inference to load it.

Verification

- `python -m compileall app scripts\train_goal_feasibility.py`
- Phase C scenario and contract checks
- Phase C training, validation, untouched temporal test, and unseen-user test
- Artifact reload and metadata verification
- `git diff --check`

## Model 3 — Subscription usage and cancellation intelligence

Status

✅ Completed

Completed

- Built quarterly subscription observation snapshots using only pre-cutoff
  transaction features and a three-month observed future window.
- Used deterministic observed payment-engagement labels because no genuine
  subscription lifecycle labels exist in the reference ledger.
- Trained and evaluated the accepted `HistGradientBoostingClassifier`
  artifact at `financial_subscription_usage/v1.0`.
- Added temporal and unseen-user evaluation, baseline metrics, leakage
  metadata, artifact reload metadata, and `subscription_usage_final_evaluation_report.json`.
- Integrated transactional engagement status into detected recurring-payment
  responses while excluding `USER_ADDED` records from ML inference.
- Added authenticated cancellation simulation using the existing unified
  commitment engine and frozen cash-flow forecast; no persisted cancellation
  occurs.
- Added frontend API typing and honest status subtitle wiring without a page
  redesign.

Verification

- Model 3 target, leakage, temporal split, baseline, and artifact tests
- Recurring-payment CRUD and tenant-isolation tests
- `python -m compileall app scripts`
- `git diff --check`
- Artifact reload and metadata verification
