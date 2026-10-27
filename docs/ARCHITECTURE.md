# FinSight — System Architecture Specification

FinSight is a production-grade Financial Exposure Intelligence System designed to give individuals and financial planners deep, explainable visibility into recurring commitments, true exposure risk, cash flow trajectories, and financial goals.

The system is built with **FastAPI** (Python), **React** (TypeScript + Vite + TailwindCSS), **PostgreSQL** (with Alembic migrations), and a dedicated **Machine Learning layer** containing 4 production models and auxiliary analytical engines.

---

## 1. High-Level Architecture Flow

```
+-------------------------------------------------------------------------+
|                              React Frontend                             |
|  (Dashboard, Intelligence, Commitments, Simulator, Assistant, Settings) |
+-------------------------------------------------------------------------+
                                    │
                                    │ HTTPS / REST (JWT Bearer Token)
                                    ▼
+-------------------------------------------------------------------------+
|                         FastAPI Router (/api/v1)                        |
|  Auth | Dashboard | Commitments | Goals | Simulator | Copilot | ML     |
+-------------------------------------------------------------------------+
       │                             │                         │
       ▼                             ▼                         ▼
+---------------------+     +--------------------+     +-------------------+
| Auth & Tenant Core  |     |  Domain Services   |     | Machine Learning  |
| - JWT Security      |     | - UnifiedCommitment|     | - Model 1:Cashflow|
| - AuthUser / User   |     | - ExposureService  |     | - Model 2:Goals   |
| - Isolated Ledgers  |     | - TrialIntelligence|     | - Model 3:Usage   |
+---------------------+     | - SimulatorService |     | - Model 4:Shortfal|
       │                    +--------------------+     +-------------------+
       ▼                             │                         │
+---------------------+              ▼                         ▼
| PostgreSQL / Alembic|     +--------------------+     +-------------------+
| - users             |     | Digital Twin State |     | Versioned Models  |
| - transactions      |     | - ScenarioBuilder  |     | - saved_models/   |
| - recurring_payments|     | - FinancialProfile |     | - feature pipeline|
| - financial_goals   |     +--------------------+     +-------------------+
+---------------------+
```

---

## 2. Core Architectural Subsystems

### 2.1 Multi-Tenant Authentication & Ledger Isolation
- User accounts are authenticated via JWT bearer tokens.
- `AuthUser` maps 1-to-1 to a dedicated financial identity `User` (`AUTH{id:08d}`).
- Transaction ledgers are strictly segregated: queries filter by `user_id == current_user.user_id`.
- Unauthenticated requests or cross-tenant ID access attempts return `401 Unauthorized` or `403 Forbidden`.

### 2.2 Transaction Ingestion & Profile Synchronization
- **Transaction Ledger**: Ingested via CSV upload or API.
- **Normalization Pipeline**: Automatically deduplicates rows by timestamp, amount, and merchant name, classifies transactions (`income`, `expense`, `subscription`, `emi`, `bnpl`), and normalizes merchant entities.
- **Profile Synchronization**: `FinancialProfileSyncService` computes updated financial capacity, exposure scores, and cash balances upon each ingestion batch.

### 2.3 Unified Commitment Engine
- Managed by `UnifiedCommitmentService` backed by the `recurring_payments` database table.
- Canonical source of truth for recurring financial commitments across all categories (Subscriptions, EMIs, Loans, BNPL, Insurance, Utilities).
- Distinguishes between `DETECTED` (algorithmic recurring payment detection with confidence gates) and `USER_ADDED` (manual user commitments).
- Enforces strict business rules: income/salary transactions are strictly prohibited from becoming commitments; one-off transactions without recurring frequency are excluded.

### 2.4 Financial Exposure & Health Engine
- Orchestrated by `ExposureService`.
- **Exposure Formula**:
  $$\text{Exposure Score} = \left( \frac{\text{Monthly Total Commitments}}{\text{Monthly Financial Capacity}} \right) \times 100$$
- **Exposure Risk Bands**: Minimal ($0\%$), Low ($1\text{--}40\%$), Moderate ($41\text{--}100\%$), High ($101\text{--}120\%$), Critical ($>120\%$).
- **Financial Health Score**: Composite score ($0\text{--}100$) calculated across 6 explainable factors: Exposure, Payment Behaviour, AutoPay Coverage, Commitment Diversity, Liquidity Buffer, and Stability.
- Produces prioritized, explainable recommendations with quantified monthly and annual savings impacts.

### 2.5 What-If Digital Twin Simulator
- Managed by `SimulatorService` and `ScenarioBuilder`.
- Performs non-destructive in-memory simulations of financial decisions on the user's digital twin:
  - Adding or modifying recurring commitments (Subscriptions, EMIs, BNPL).
  - Simulating commitment cancellations.
  - Simulating income shifts or bonus windfalls.
  - Simulating lump-sum major expenses.
- Computes before/after deltas for exposure scores, available monthly capacity, and financial health trajectories without altering actual ledger records.

### 2.6 Conversational Copilot / AI Assistant
- Integrated via `CopilotService` with abstract LLM provider support (`LLMProvider`).
- Implements secure intent detection, personal financial context injection, and structured tool calling:
  - Tools include `get_user_financial_summary`, `get_user_commitments`, `get_exposure_analysis`, `get_cashflow_forecast`, and `simulate_scenario`.
  - Tool calls execute strictly within the authenticated user's session boundary.
  - Multi-turn conversation history is persisted in `conversations` database records.

### 2.7 Machine Learning Architecture
- **Model 1 (Cash Flow Forecast)**: Multi-component tabular regression predicting next-month income, committed spending, variable spending, and net liquidity using XGBoost and rolling baselines.
- **Model 2 (Goal Feasibility)**: HistGradientBoosting classifier evaluating whether active savings goals can be met within target deadlines.
- **Model 3 (Subscription Usage)**: Multi-class classifier predicting payment engagement (`ACTIVE`, `MODERATE`, `UNDER_UTILIZED`) to suggest cancellations.
- **Model 4 (Shortfall Prediction)**: Binary classifier forecasting next-month negative cash balances.
- **Auxiliary Engines**: Anomaly Detection (`IsolationForest`), Distress Risk (`RandomForest`), Long-Term Exposure Forecast, and Behavioral Persona Clustering (`KMeans`).

---

## 3. Strict Architectural Rules

1. **Deterministic Primacy**: All balance-sheet arithmetic is calculated deterministically via domain services (`UnifiedCommitmentService`, `ExposureService`). ML models never perform balance sheet arithmetic.
2. **No Business Logic in Endpoints**: Endpoints in `app/api/v1/endpoints/` only validate input, authenticate sessions, invoke services, and return typed schemas.
3. **Internal Calls**: Services communicate via direct Python method calls, never internal HTTP loops.
4. **Data Isolation**: Authentic user personal ledgers are strictly segregated from training reference populations.