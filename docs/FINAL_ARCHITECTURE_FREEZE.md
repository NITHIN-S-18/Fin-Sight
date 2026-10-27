# FinSight — Final Architecture Freeze (Phase 0)

## Document Metadata
- **Status:** FROZEN & RATIFIED
- **Date:** 2026-10-07
- **Phase:** Phase 0 (Architecture Freeze)
- **Scope:** System architecture, ML model definitions, generalized recurring engine, unified commitment layer, persistence contracts, category taxonomy, tenant isolation, compatibility boundaries, and execution roadmap.

---

## 1. Final Product Architecture & System Identity

FinSight is a **Financial Exposure Intelligence System**, not a generic personal expense tracker. The core objective of the platform is to evaluate how recurring financial obligations, debt commitments, and fixed overhead constrain a user's future financial flexibility, and to forecast upcoming cash position using machine learning.

### End-to-End User Journey

```text
REGISTER
  │
  ▼
LOGIN (JWT Issuance & Financial User Profile Mapping)
  │
  ▼
UPLOAD PERSONAL TRANSACTION CSV
  │
  ▼
VALIDATE + CLEAN (Deduplication, normalization, fingerprinting)
  │
  ▼
STORE TRANSACTIONS (Strictly scoped to authenticated financial_user_id)
  │
  ▼
DETECT RECURRING PAYMENTS (Generalized multi-category pattern recognition)
  │
  ▼
COMBINE DETECTED + USER-ADDED RECURRING PAYMENTS (Non-destructive override model)
  │
  ▼
UNIFIED FINANCIAL COMMITMENT ENGINE (Authoritative calculation of committed overhead)
  │
  ▼
FINANCIAL EXPOSURE + FINANCIAL HEALTH (Deterministic metrics & buffer analysis)
  │
  ▼
FOUR FINANCIAL INTELLIGENCE MODELS (Cash Flow, Goals, Subscriptions, Shortfall)
  │
  ▼
DASHBOARD + INTELLIGENCE + ACTIONABLE INSIGHTS (Interactive UI & Copilot)
```

### Reference vs. Authenticated User Boundary
- **Reference Datasets:** Synthetic/benchmark datasets (e.g. `finsight_ml_dataset_v3.csv` or `finsight_dataset_v2.csv`) exist exclusively for offline ML training, algorithm benchmarking, and cross-validation.
- **Authenticated User Ledgers:** Authenticated user accounts start with an empty ledger and populate transactions solely through verified user CSV uploads. Under no circumstances may reference or synthetic records be seeded, mixed, or leaked into an authenticated user's ledger or commitment calculations.

---

## 2. Final Four ML Models — Contract Freeze

The platform's predictive intelligence is strictly defined around four core user questions. All four models must follow rigorous ML engineering standards:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FINSIGHT 4-MODEL ML ARCHITECTURE                      │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│ Model                   │ Core Question           │ Primary Technique       │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ 1. Cash Flow Forecast   │ How much will I have?   │ XGBoost Regressor       │
│ 2. Goal Feasibility     │ Can I achieve my goal?  │ Cash Flow Arithmetic    │
│ 3. Subscription Usage   │ What could I save?      │ Transactional Cadence   │
│ 4. Shortfall Prediction │ Will I run short?       │ XGBoost Classifier      │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

### Model 1 — Cash Flow Forecasting
- **Core User Question:** *"How much money will I likely have next month?"*
- **Prediction Targets (Next Month $T+1$):**
  1. `expected_income`: Forecasted total inflow from recurring and regular sources.
  2. `expected_committed_expenses`: Forecasted fixed outflows derived from the Unified Commitment Engine.
  3. `expected_variable_expenses`: Forecasted discretionary spending.
  4. `expected_total_expenses`: $\text{expected\_committed\_expenses} + \text{expected\_variable\_expenses}$.
  5. `expected_net_cash`: $\text{expected\_income} - \text{expected\_total\_expenses}$.
- **Algorithm Policy:**
  - Primary algorithm: **XGBoost Regressor** (with hyperparameter tuning over temporal folds).
  - Mandatory baseline: **Naive Historical Baseline** (e.g., preceding month actual net cash or 3-month trailing moving average).
  - Model selection rule: XGBoost must not be deployed unless it empirically outperforms the naive baseline on validation/test sets.
- **Evaluation Metrics:**
  - Mean Absolute Error (MAE)
  - Root Mean Squared Error (RMSE)
  - Coefficient of Determination ($R^2$)
  - Relative improvement percentage over baseline: $\frac{\text{MAE}_{\text{naive}} - \text{MAE}_{\text{model}}}{\text{MAE}_{\text{naive}}} \times 100\%$
- **Leakage Prevention:**
  - Strict temporal ordering: Features computed from ledger snapshots through month $T$; target evaluated strictly from month $T+1$.
  - Preprocessing (scalers, imputers) fitted exclusively on training splits.

### Model 2 — Financial Goal Feasibility
- **Core User Question:** *"Can I realistically achieve my financial goal?"*
- **Inputs Provided by User:**
  - `goal_name` (e.g., "New Laptop", "Emergency Reserve")
  - `target_amount` (e.g., ₹80,000)
  - `target_date` or `timeframe_months` (e.g., June 2027 or 12 months)
- **Mathematical Specification:**
  $$\text{remaining\_months} = \max\left(1, \Delta\text{months}(\text{now}, \text{target\_date})\right)$$
  $$\text{required\_monthly\_saving} = \left\lceil \frac{\text{target\_amount} - \text{current\_saved}}{\text{remaining\_months}} \right\rceil$$
  $$\text{expected\_monthly\_saving} = \min\left(\text{required\_monthly\_saving}, \text{Model 1 Expected Net Cash}\right)$$
  $$\text{additional\_monthly\_needed} = \max\left(0, \text{required\_monthly\_saving} - \text{expected\_monthly\_saving}\right)$$
- **Feasibility Status:**
  - `Achievable`: When $\text{additional\_monthly\_needed} == 0$.
  - `Needs Adjustment`: When $\text{additional\_monthly\_needed} > 0$.
- **Optimization Strategy:**
  - Recommends adjustments **only** in variable/discretionary categories (Dining, Shopping, Entertainment, Travel).
  - Committed obligations (Rent, EMIs, Insurance, Utilities) are **strictly protected** and must never be suggested for reduction.
- **No Fabricated Probabilities:**
  - Feasibility is determined by cash flow coverage and arithmetic gap analysis.
  - No synthetic percentages (e.g., "84% Probability") may be rendered unless a genuinely calibrated probabilistic model is trained and verified.

### Model 3 — Subscription Usage & Cancellation Intelligence
- **Core User Question:** *"Which subscriptions appear under-utilized, and what could I save by cancelling them?"*
- **Data Grounding Constraint:**
  - Inferences must rely solely on **transactional and behavioural evidence** (billing regularity, payment cadence, renewal gaps, charge consistency).
  - Never fabricate telemetry: No claims of "hours watched", "songs played", "app screen time", or "gym attendance".
- **Engagement Classification:**
  - `Active`: Highly regular cadence, stable payment amounts, uninterrupted renewal.
  - `Moderate`: Mild variance in payment interval or billing anomalies.
  - `Under-utilized`: Extended transaction gaps, price tier jumps without activity, duplicate merchant categories, or erratic billing patterns.
- **Cancellation Simulation Engine:**
  - Operates completely in-memory (never initiates real bank cancellations).
  - Simulates:
    1. Current monthly commitments
    2. Post-cancellation commitments ($\text{Current} - \sum \text{Selected Monthly Cost}$)
    3. Monthly savings & Annualized savings ($\text{Monthly} \times 12$)
    4. Impact on available net cash buffer
    5. Impact on Model 2 Goal Feasibility (closing the monthly gap)
    6. Impact on Model 4 Shortfall Risk

### Model 4 — Financial Shortfall Prediction
- **Core User Question:** *"Am I likely to run short of money next month?"*
- **Binary Target:**
  $$Y_{T+1} = \mathbb{I}\left(\text{Actual Net Cash Flow in Month } T+1 < 0\right)$$
- **Candidate Feature Space:**
  - Income stability score & income volatility coefficient
  - Discretionary spending variance
  - Recurring commitment burden ratio ($\frac{\text{Commitments}}{\text{Income}}$)
  - Historical shortfall frequency (past occurrences where net cash $< 0$)
  - Model 1 predicted net cash buffer
  - Sudden commitment delta ($\text{Commitments}_T - \text{Commitments}_{T-1}$)
- **Algorithm Policy:**
  - Primary algorithm: **XGBoost Classifier**.
  - Mandatory baseline: **Class Prevalence / Prior Probability Baseline**.
- **Evaluation Metrics:**
  - Precision, Recall, and F1 Score (with priority on Recall to avoid missing critical insolvency events)
  - ROC-AUC and Precision-Recall AUC (PR-AUC)
  - Calibration: Brier Score and calibration curve if probabilistic output is displayed.
  - Zero ungrounded "confidence" metrics.

---

## 3. Recurring Payment Architecture & Contract

The recurring obligations system extends far beyond basic digital subscriptions to encompass all fixed recurring commitments:

### Scope of Supported Recurring Categories
1. **Subscriptions:** Streaming, software (SaaS), cloud storage, news, fitness memberships.
2. **EMI & Loans:** Home loans, personal loans, vehicle loans, education loans.
3. **BNPL:** Split-payment instalment schedules (Klarna, Affirm, Simpl, LazyPay).
4. **Housing & Living:** House rent, society maintenance, lease payments.
5. **Insurance:** Health insurance, life term insurance, motor insurance premiums.
6. **Utilities:** Electricity, water, cooking gas (piped/cylinder).
7. **Connectivity:** Broadband internet, mobile post-paid / regular recharges.
8. **Investments / Wealth:** Systematic Investment Plans (SIP), recurring deposits (RD).
9. **Education:** School/college fees, coaching fees.

### Normalized Recurring Payment Schema
Every recurring payment entity must conform to the following schema:

```python
class RecurringPaymentRecord:
    id: str  # Unique UUID
    financial_user_id: str  # Foreign key to user
    name: str  # e.g., "HDFC Home Loan EMI", "Netflix", "House Rent"
    category: str  # "emi" | "subscription" | "bnpl" | "rent" | "insurance" | "utility" | "investment" | "other"
    amount: float  # Nominal recurring amount (must be positive)
    frequency: str  # "monthly" | "quarterly" | "annual" | "weekly" | "biweekly"
    monthly_equivalent_amount: float  # Normalized monthly burden
    last_payment_date: date | None
    next_expected_date: date | None
    status: str  # "active" | "paused" | "completed" | "cancelled"
    confidence: float  # 0.0 to 1.0
    confidence_level: str  # "high" | "low"
    source: str  # "DETECTED" | "USER_ADDED"
    is_active: bool  # Active flag for commitment calculation
    transaction_evidence_ids: list[str]  # IDs of supporting transactions
    user_override_id: str | None  # Pointer if user has customized this detection
    created_at: datetime
    updated_at: datetime
```

---

## 4. DETECTED vs. USER_ADDED Semantics & Overrides

### Source Partitioning
1. `source = "DETECTED"`:
   - Generated algorithmically by pattern analysis of ingested transactions.
   - Tied directly to transaction fingerprint evidence.
   - Ephemeral or regenerated upon ledger re-sync.
2. `source = "USER_ADDED"`:
   - Created manually by the user (e.g. cash rent, employer-deducted insurance, newly set up recurring obligations).
   - Has zero transaction evidence requirement.
   - Fully persistent across transaction re-imports.

### Non-Destructive Override Model
When a user edits a detected recurring payment (e.g. correcting the name, adjusting the amount, changing the billing date):
- **Rule:** The underlying `DETECTED` record and its transaction evidence must **NEVER** be destroyed or mutated in-place.
- **Implementation:** An explicit user override record is created linked to the detected entity.
- The Unified Commitment Engine loads the detected record, applies the user's explicit overrides, and marks the item as user-confirmed.

---

## 5. Recurring Detection Rules & Low-Confidence Policy

### Occurrence & Regularity Rules
- **High-Confidence Detection ($\ge 3$ Occurrences):**
  - Minimum of 3 occurrences matching the same merchant / description pattern.
  - Consistent time interval ($\Delta t \pm 5$ days of nominal frequency).
  - Amount variance within $\pm 10\%$ (or exact match for fixed-fee services).
  - Status: Automatic inclusion in Unified Commitment Engine.
- **Low-Confidence Detection ($2$ Occurrences):**
  - Exactly 2 occurrences exhibiting recurring interval signals.
  - Confidence marked as `low` ($< 0.70$).
  - Display label: *"Possible recurring payment (2 occurrences detected)"*.

### Authoritative Exposure Policy for Low-Confidence Detections
- **Mandatory Rule:** Low-confidence detections **MUST NOT** automatically affect authoritative financial exposure, financial health scores, or Model 1 committed expense totals.
- They remain visible in the UI under a distinct "Needs Review" filter.
- Once confirmed by the user (or upon observing a 3rd successful billing event), they are promoted to high-confidence and enter the commitment calculation.

---

## 6. Trial & Authorization Intelligence

### Detection Pattern
```text
Small Transaction (₹1 or ₹2)
  │ (Auth / Verification Hold)
  ▼
Merchant Activity / Registration
  │
  ▼
Potential Free Trial Window (7, 14, 30 days)
  │
  ▼
Upcoming Full Recurring Charge Alert
```

### Protocol & Terminology
1. **Never Assume Definitively:** Micro-transactions of ₹1/₹2 can be account validations, mandate setups, or temporary holds.
2. **Standard Terminology:** Display as *"Possible free trial / authorization detected"*.
3. **Inference Guard:** A future billing date is estimated only if the merchant has an established standard trial window (e.g., 30-day trial for Prime/Spotify) or explicit transaction text.
4. **Channel Policy:** Alerts are delivered via **in-app notification cards only**. No external SMS, email, or push notifications will be constructed in Phase 0.

---

## 7. Unified Financial Commitment Engine

### The Authoritative Calculation Path
In the legacy system, commitments were calculated independently and duplicated across `SubscriptionService`, `EmiService`, `BnplService`, and inline dashboard code.

Under the frozen architecture, a single **Unified Commitment Engine** serves as the sole source of truth:

```text
┌──────────────────────────────────────┐     ┌──────────────────────────────────────┐
│     DETECTED RECURRING PAYMENTS      │     │     USER-ADDED RECURRING PAYMENTS    │
│  (Filtered: High Confidence / Conf)  │     │          (Filtered: Active)          │
└──────────────────┬───────────────────┘     └──────────────────┬───────────────────┘
                   │                                            │
                   └─────────────────────┬──────────────────────┘
                                         ▼
                   ┌────────────────────────────────────────────┐
                   │        UNIFIED COMMITMENT ENGINE           │
                   │  - Frequency normalization to monthly      │
                   │  - User override reconciliation            │
                   │  - Deduplication across categories         │
                   └─────────────────────┬──────────────────────┘
                                         ▼
                   ┌────────────────────────────────────────────┐
                   │    MONTHLY TOTAL COMMITTED EXPENSES        │
                   └──────┬──────────────────────┬──────────────┘
                          │                      │
             ┌────────────┴──────────┐    ┌──────┴────────────────────┐
             ▼                       ▼    ▼                           ▼
      FINANCIAL EXPOSURE      FINANCIAL   MODEL 1 FORECAST     WHAT-IF / COPILOT
      & HEALTH ENGINES        DASHBOARD   FEATURE PIPELINE     SIMULATION BASELINE
```

### Existing Services as Adapters
During the transition, existing services (`SubscriptionService`, `EmiService`, `BnplService`) will be retained as read adapters, delegating their total calculations to the Unified Commitment Engine to guarantee mathematical consistency across all endpoints.

---

## 8. Goal Persistence Contract

Financial goals must be persisted entities tied to the authenticated user's financial profile.

### Minimum Entity Schema
```python
class FinancialGoal:
    id: str  # UUID
    financial_user_id: str  # Scoped to authenticated user
    title: str  # Goal name (e.g., "Emergency Fund")
    category: str  # "Savings", "Tech", "Travel", "Vehicle", "Home", "Other"
    target_amount: float  # Required total
    current_saved: float  # Current progress (defaults to 0.0)
    target_date: date  # Target completion date
    status: str  # "in_progress" | "achieved" | "archived"
    created_at: datetime
    updated_at: datetime
```

### Supported Operations
- `Create`: Post new goal with validation against target date $> \text{today}$.
- `Read`: List user goals and retrieve feasibility breakdown.
- `Update`: Modify target amount or target date.
- `Delete/Deactivate`: Remove or archive goal.

---

## 9. Protected vs. Discretionary Category Policy

To prevent the system from giving unrealistic financial advice, categories are categorized into strict classes:

### Essential & Committed (Protected — NEVER suggest reduction)
- **Rent / Mortgage**
- **EMIs & Loan Repayments**
- **Insurance Premiums** (Health, Life, Vehicle)
- **Utilities** (Electricity, Water, Cooking Gas)
- **Essential Recurring Bills** (Broadband, Municipal taxes)
- **Core Groceries & Medicine**

### Variable & Discretionary (Adjustable — Primary optimization targets)
- **Dining Out & Food Delivery** (Cafes, Swiggy, Zomato, Restaurants)
- **Shopping & Apparel** (Fashion, Electronics, Impulse retail)
- **Entertainment & Leisure** (Movies, Gaming, Events, Clubs)
- **Discretionary Travel & Vacations** (Flights, Leisure hotels, Weekend trips)
- **Non-essential Subscriptions** (Multiple overlapping streaming services)

---

## 10. Old ML Architecture — Compatibility & Deprecation Strategy

### Inventory of Existing ML Components
The repository currently houses the Phase 9 legacy ML architecture:
- **Engines:**
  - `FinancialDistressEngine` (`backend/app/ml/engines/distress_engine.py`)
  - `ExposureForecastEngine` (`backend/app/ml/engines/exposure_forecast_engine.py`)
  - `BehaviourIntelligenceEngine` (`backend/app/ml/engines/behaviour_engine.py`)
  - `FinancialAnomalyEngine` (`backend/app/ml/engines/anomaly_engine.py`)
- **Fusion Layer:**
  - `FinancialIntelligenceFusionLayer` (`backend/app/ml/fusion/intelligence_fusion.py`)
  - `AIInsightsLayer` (`backend/app/ml/insights/insights_generator.py`)
- **Endpoints in `backend/app/api/v1/endpoints/ml.py`:**
  - `GET /api/v1/ml/distress/{user_id}`
  - `GET /api/v1/ml/exposure/{user_id}`
  - `GET /api/v1/ml/persona/{user_id}`
  - `GET /api/v1/ml/anomaly/{user_id}`
  - `GET /api/v1/ml/intelligence/{user_id}`
- **Frontend Usage:**
  - `frontend/src/api/client.ts` defines `intelligenceApi.get()` targeting `/ml/intelligence/{financialUserId}`.
  - `frontend/src/app/IntelligencePage.tsx` currently invokes `intelligenceApi.get()` on load for exposure context.
- **Test Dependencies:**
  - `tests/test_ml_quality.py`
  - `tests/test_intelligence_fusion.py`
  - `tests/test_api_smoke.py`
  - `tests/test_phase13_complete_flow.py`

### Freeze Decision: Strict Non-Deletion in Phase 0
- **Policy:** **DO NOT delete or disable these files during Phase 0.**
- They remain operational as a compatibility bridge so current test suites and frontend flows continue to function without disruption.
- **Migration Plan:** In Phase 9 (Final Intelligence API Integration), new product-aligned endpoints will be introduced. In Phase 13, frontend calls will be redirected. Only after full verification in Phase 14 will the legacy Phase 9 engines be formally archived.

---

## 11. Baseline Evaluation Policy

For every predictive model (Model 1 and Model 4), a complex model must never be assumed to be superior simply because it uses gradient boosting.

1. **Regression (Model 1):**
   - Must evaluate against:
     - Naive $T-1$ actual value persistence.
     - 3-month trailing moving average.
   - Deliverable: Comparative metrics table showing MAE, RMSE, and $R^2$ side-by-side.
2. **Classification (Model 4):**
   - Must evaluate against:
     - Majority-class (zero-rule) baseline.
     - Stratified random baseline.
   - Deliverable: Confusion matrix, Precision, Recall, and PR-AUC relative to the baseline prevalence rate.

---

## 12. Training Data & Reference Boundaries

1. **Dataset Directory:**
   - Reference data location: `backend/app/data/ml_dataset_v3/` (or generated via `scripts/generate_ml_dataset.py`).
   - Artifact storage: `backend/app/ml/saved_models/`.
2. **Separation Rule:**
   - Training scripts consume only reference files specified via `ML_REFERENCE_DATA_DIR`.
   - Production FastAPI request handlers consume transactions strictly from the authenticated database (`Transaction` table filtered by `financial_user_id`).
   - No offline training script may write into the application database.

---

## 13. Authentication & Tenant Isolation Rules

1. **Identity Grounding:**
   - Every protected request must extract user identity from the verified JWT bearer token (`sub` claim $\rightarrow$ `AuthUser.id` $\rightarrow$ `User.id`).
   - Path parameters containing `user_id` or `financial_user_id` must be validated using `require_financial_user(requested_id, current_user)`.
   - The backend must **never trust** client-supplied IDs without cryptographic verification.
2. **Data Isolation:**
   - All queries for transactions, recurring payments, goals, snapshots, simulations, and Copilot context must include `WHERE financial_user_id = :authenticated_user_id`.
   - Database foreign keys must enforce relational integrity to the owner.

---

## 14. API Design Principles

1. **Domain-Driven Routing:**
   - Endpoints must be structured around product concepts rather than internal ML architecture:
     - `/api/v1/recurring-payments/` (Detection, listing, overrides, manual creation)
     - `/api/v1/goals/` (CRUD operations for user goals)
     - `/api/v1/intelligence/forecast` (Model 1 Cash flow forecast)
     - `/api/v1/intelligence/goals` (Model 2 Goal feasibility evaluation)
     - `/api/v1/intelligence/subscriptions` (Model 3 Cadence & cancellation simulation)
     - `/api/v1/intelligence/shortfall` (Model 4 Shortfall risk prediction)
     - `/api/v1/intelligence/overview` (Combined 4-model summary)
2. **Standardization:**
   - Pydantic v2 schemas for all request/response bodies.
   - Unified RFC 7807 problem details error format.
   - No API endpoint changes are executed in Phase 0.

---

## 15. Performance Principles

1. **Indexing:**
   - Composite indexes on `Transaction`: `(financial_user_id, transaction_date)` and `(financial_user_id, merchant_name)`.
   - Index on `RecurringPayment`: `(financial_user_id, is_active)`.
   - Index on `Goal`: `(financial_user_id, status)`.
2. **Caching & Reusability:**
   - Feature snapshots cached per ledger version (`import_hash`).
   - Model weights loaded once at application bootstrap into memory (singleton manager); no disk I/O per HTTP request.
   - Batch database inserts for CSV transactions to avoid $N+1$ latency.

---

## 16. Phase Dependency Order (Frozen Sequence)

```text
PHASE 0  ──► Architecture Freeze (Current Phase)
  │
PHASE 1  ──► Generalized Recurring Detection (Multi-category pattern engine)
  │
PHASE 2  ──► User-Added Recurring Payments (Manual entry, persistence, overrides)
  │
PHASE 3  ──► Trial / Authorization Intelligence (Micro-auth detection, in-app alerts)
  │
PHASE 4  ──► Unified Commitment Engine (Authoritative single-source calculation)
  │
PHASE 5  ──► Cash Flow Forecasting (Model 1: XGBoost + Baseline + Evaluation)
  │
PHASE 6  ──► Goal Feasibility (Model 2: Persisted goals, cash flow arithmetic, variable cuts)
  │
PHASE 7  ──► Subscription Usage & Cancellation Intelligence (Model 3: Simulation engine)
  │
PHASE 8  ──► Financial Shortfall Prediction (Model 4: XGBoost + Baseline + Calibration)
  │
PHASE 9  ──► Final Intelligence API Integration (Unified product endpoints)
  │
PHASE 10 ──► Cross-System Integration (Dashboard, What-If, Copilot synchronisation)
  │
PHASE 11 ──► Performance Optimization (Indexing, snapshot caching, query tuning)
  │
PHASE 12 ──► Security + Full Regression (Tenant isolation tests, edge cases, auth check)
  │
PHASE 13 ──► Final Frontend Integration (Connect frozen React pages to real APIs)
  │
PHASE 14 ──► Final Documentation + Launch Verification (Verification sign-off)
```

### Dependency Rationale
- **Phase 1 & 2 before Phase 4:** The Unified Commitment Engine cannot be finalized without having both detected recurring items and user-added items standardized.
- **Phase 4 before Models (Phases 5–8):** All 4 ML models depend directly on authoritative commitment calculations from the Unified Commitment Engine.
- **Model 1 before Model 2 & 4:** Goal feasibility and Shortfall prediction both consume Model 1's forecasted cash flow output.
- **Frontend Integration (Phase 13) after API & System Testing (Phases 9–12):** Guarantees the frontend connects only to fully stable, tested, and performance-tuned backend endpoints.

---

## 17. Identified Architectural Risks & Mitigation

1. **Commitment Metric Drift During Migration:**
   - *Risk:* Legacy services calculating different totals than the new Unified Commitment Engine while both coexist.
   - *Mitigation:* In Phase 4, refactor legacy services to act strictly as facades forwarding to the Unified Commitment Engine.
2. **Cold-Start for New Users with Short History:**
   - *Risk:* A user uploading only 1 month of transactions cannot support 3-occurrence detection or longitudinal forecasting.
   - *Mitigation:* Explicit cold-start guards: fallback to manual user-entered commitments and clear UI status indicating minimum data requirements.
3. **Distribution Shift Between Synthetic & Real Ledgers:**
   - *Risk:* ML models overfitted to synthetic generator patterns.
   - *Mitigation:* Baseline comparison requirement and temporal cross-validation on realistic CSV transaction schemas.
4. **Digital Twin Exposure Clamping:**
   - *Risk:* Simulator previously clamping exposure at 100% while Exposure Engine is uncapped.
   - *Mitigation:* Reconcile simulator formula in Phase 10 to use uncapped exposure metrics matching business rules.

---

## 18. Explicit Non-Goals for Phase 0

- **NO** database migrations created or executed.
- **NO** database tables created, altered, or dropped.
- **NO** backend endpoints created, modified, or deleted.
- **NO** frontend components or styling modified.
- **NO** models retrained or artifacts overwritten.
- **NO** dataset files generated or deleted.
- **NO** legacy files deleted.
- **NO** git commits or pushes performed.

---

## 19. Architectural Ratification

This document serves as the formal architectural freeze for the remainder of the FinSight implementation. All subsequent phases must conform to the contracts, definitions, and sequencing established herein.
