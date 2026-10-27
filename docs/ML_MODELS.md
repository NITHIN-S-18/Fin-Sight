# FinSight — Machine Learning Models Specification

This document provides the authoritative technical specification, training methodology, evaluation metrics, and runtime serve contracts for all machine learning models in **FinSight — Financial Exposure Intelligence System**.

---

## 1. Machine Learning Architectural Principles

FinSight enforces a strict boundary between **deterministic business logic** and **statistical machine learning**:

1. **Deterministic Primacy**: All financial arithmetic (e.g. total monthly commitments, bank balances, payment schedules, and what-if delta calculations) is calculated deterministically via domain services (`UnifiedCommitmentService`, `ExposureService`). ML models never perform balance sheet arithmetic.
2. **Temporal Supervision**: All training labels are observed from longitudinal future horizons ($T \to T+1$ or $T \to T+3$). No synthetic data artifacts or target leakage are used in feature engineering.
3. **Train-Only Preprocessing**: Preprocessing scalers and encoders are strictly fitted on training splits only and frozen in artifact pipelines.
4. **Tenant Isolation**: Model inference executes strictly within the authenticated user's session boundary. Reference training populations are kept in isolated storage.
5. **Fallback Safety**: Every model has a deterministic or statistical baseline fallback if the artifact is missing, uncalibrated, or if a user has insufficient transaction history.

---

## 2. Model 1: Cash Flow & Multi-Component Forecast

- **Purpose**: Forecasts next-month financial components (Income, Committed Expenses, Variable Expenses, and Net Cash Flow) to project user liquidity.
- **Task Type**: Multi-target tabular regression.
- **Model Architecture**: Multi-component regression combining XGBoost Regressor (`v3.4.1`) and HistGradientBoosting alongside rolling statistical baselines (3-month and 6-month exponentially weighted averages).
- **Artifact Path**: `backend/app/ml/saved_models/cash_flow_forecast/v1.0/model.pkl`
- **Metadata Path**: `backend/app/ml/saved_models/cash_flow_forecast/v1.0/metadata.json`
- **Training Script**: `backend/scripts/train_cashflow_forecast.py`, `backend/scripts/final_cashflow_evaluation.py`
- **Evaluation Report**: `cashflow_final_evaluation_report.json`, `cashflow_xgboost_report.json`

### Selected Production Implementation (Accepted Hybrid)

In production runtime inference (`CashflowForecastService`), the model employs an **Accepted Hybrid** strategy governed by the validated artifact metadata (`backend/app/ml/saved_models/cash_flow_forecast/v1.0/metadata.json`):

1. **Income Forecasting**: **`six_month_average`** (rolling baseline). Offline evaluation showed the 6-month historical rolling average achieves superior stability and generalizability on income ($R^2 = 0.9474$, MAE: 6,746.64) compared to unconstrained regression.
2. **Committed-Expense Forecasting**: **`three_month_average`** (rolling baseline). The 3-month rolling window captures recent commitment obligations with highest fidelity ($R^2 = 0.5811$, MAE: 2,917.63).
3. **Variable-Expense Forecasting**: **`ml` (`HistGradientBoostingRegressor`)**. The trained machine learning model outperformed rolling baselines (MAE: 2,220.14 vs baseline 2,329.65; $R^2 = 0.6797$ vs baseline 0.6444), successfully capturing non-linear discretionary spending patterns.
4. **Total Expenses & Net Cash**: Total expenses are computed as $\text{Committed} + \text{Variable}$, and Net Cash Flow as $\text{Income} - \text{Total Expenses}$.

### Performance & Evaluation Metrics (Untouched Test Set)

| Target Component | Selected Forecaster | Algorithm / Strategy | Test $R^2$ | Test MAE |
| :--- | :--- | :--- | :---: | :---: |
| **Income** | `six_month_average` | 6-Month Rolling Baseline | **0.9474** | 6,746.64 |
| **Committed Expenses** | `three_month_average` | 3-Month Rolling Baseline | **0.5811** | 2,917.63 |
| **Variable Expenses** | `ml` | HistGradientBoostingRegressor | **0.6797** | 2,220.14 |
| **Net Cash Flow** | Derived | $\text{Income} - (\text{Committed} + \text{Variable})$ | **0.8842** | 5,920.10 |

### Runtime Serve Contract
- **Service**: `CashflowForecastService` (`backend/app/services/cashflow_forecast_service.py`)
- **API Endpoint**: `GET /api/v1/ml/forecast/cashflow/{user_id}`
- **Fallback**: If transaction history is fewer than 3 months, returns deterministic rolling average with `"history_insufficient": true` notice. If the ML model artifact is unavailable, it gracefully defaults to rolling baselines across all three components.

---

## 3. Model 2: Financial Goal Feasibility Engine

- **Purpose**: Evaluates whether a user can feasibly achieve a target financial savings goal given their income trajectory, commitment obligations, and savings timeline.
- **Task Type**: Binary classification (`FEASIBLE` vs `AT_RISK`).
- **Model Architecture**: `HistGradientBoostingClassifier` with temporal feature engineering.
- **Artifact Path**: `backend/app/ml/saved_models/goal_feasibility/model-2-phase-c-v2.pkl`
- **Training Script**: `backend/scripts/train_goal_feasibility.py`
- **Evaluation Report**: `goal_feasibility_final_evaluation_report.json`

### Performance & Evaluation Metrics

| Dataset Split | Baseline Balanced Accuracy | Model 2 Balanced Accuracy | Improvement |
| :--- | :---: | :---: | :---: |
| **Validation Set** | 0.5968 | **0.6848** | +0.0880 |
| **Untouched Temporal Test** | 0.6012 | **0.6992** | +0.0980 |
| **Unseen Users (750 users)** | 0.5142 | **0.6491** | +0.1349 |

### Runtime Serve Contract
- **Service**: `GoalFeasibilityService` (`backend/app/services/goal_feasibility_service.py`)
- **API Endpoints**:
  - `POST /api/v1/goals`: Goal creation with monthly savings plan calculation
  - `GET /api/v1/goals/{id}/feasibility`: Evaluates live feasibility and required monthly savings adjustments
- **Fallback**: Rule-based feasibility comparison ($Required\ Monthly\ Savings \le Available\ Capacity \times 0.70$).

---

## 4. Model 3: Subscription Usage & Payment Engagement Intelligence

- **Purpose**: Identifies underutilized recurring payments and subscriptions based on longitudinal payment activity over 3-month quarterly observation windows.
- **Task Type**: Multiclass classification (`ACTIVE`, `MODERATE`, `UNDER_UTILIZED`).
- **Model Architecture**: `HistGradientBoostingClassifier` with median imputation.
- **Artifact Path**: `backend/app/ml/saved_models/financial_subscription_usage/v1.0/artifact.pkl`
- **Training Script**: `backend/scripts/train_subscription_usage.py`
- **Evaluation Report**: `subscription_usage_final_evaluation_report.json`

### Performance & Evaluation Metrics

| Metric | Rule Baseline | Model 3 Classifier |
| :--- | :---: | :---: |
| **Validation Balanced Accuracy** | 0.5136 | **0.6091** |
| **Untouched Test Balanced Accuracy** | 0.5276 | **0.6127** |
| **Macro F1 Score** | 0.5110 | **0.5991** |
| **Unseen User Generalization** | 0.4890 | **0.6142** |

### Runtime Serve Contract
- **Service**: `RecurringPaymentService` (`backend/app/services/recurring_payment_service.py`)
- **API Endpoint**: `POST /api/v1/recurring-payments/{id}/simulate-cancellation`
- **Contract Rules**:
  - Applied strictly to `DETECTED` recurring payments with $\ge 3$ months history.
  - `USER_ADDED` commitments are never assigned synthetic usage classifications.
  - Cancellation simulations project freed monthly cash flow and impact on active goals.

---

## 5. Model 4: Financial Shortfall Prediction

- **Purpose**: Predicts the likelihood of an authenticated user experiencing a cash shortfall (negative net cash position) in the upcoming calendar month.
- **Task Type**: Binary classification (`SHORTFALL_RISK` vs `SUFFICIENT_BUFFER`).
- **Target Definition**: Strictly observed: $Income_{T+1} - (Committed_{T+1} + Variable_{T+1}) < 0$.
- **Model Architecture**: `HistGradientBoostingClassifier` with inverse class-frequency weighting.
- **Artifact Path**: `backend/app/ml/saved_models/financial_shortfall/v1.0/model.pkl`
- **Training Script**: `backend/scripts/train_shortfall.py`
- **Evaluation Report**: `shortfall_final_evaluation_report.json`

### Performance & Evaluation Metrics

| Metric | Rule Baseline | Model 4 Classifier |
| :--- | :---: | :---: |
| **Validation Balanced Accuracy** | 0.7861 | **0.8701** |
| **Untouched Test Balanced Accuracy** | 0.7873 | **0.8957** |
| **Unseen User Balanced Accuracy** | 0.6420 | **0.7105** |
| **Test ROC-AUC** | 0.7912 | **0.9124** |

### Runtime Serve Contract
- **Service**: `ShortfallService` (`backend/app/services/shortfall_service.py`)
- **API Endpoint**: `GET /api/v1/ml/shortfall/{user_id}`
- **Outputs**: Categorical risk (`LOW`, `MODERATE`, `HIGH`), key driver factors, and actionable buffer deficit amounts.

---

## 6. Auxiliary Machine Learning Engines

In addition to the 4 core decision models, FinSight includes 4 auxiliary analytical engines located in `backend/app/ml/engines/`:

1. **Financial Distress Engine** (`financial_distress/v3.0`):
   - Supervised Random Forest Classifier predicting 30-day default risk based on payment failures and high utilization.
2. **Exposure Forecast Engine** (`exposure_forecast/v3.0`):
   - Supervised Random Forest Regressor forecasting long-term exposure trends ($T+1$ through $T+6$).
3. **Financial Anomaly Engine** (`financial_anomaly/v2.0`):
   - Unsupervised `IsolationForest` detecting anomalous spending bursts and unusual transaction spikes.
4. **Behaviour Engine** (`behaviour_engine/v2.0`):
   - Unsupervised `KMeans` clustering mapping users to behavioral personas (e.g., *Disciplined Planner*, *High Commitment Explorer*, *Debt Juggler*).

---

## 7. Model Inventory & File Registry

```
backend/app/ml/saved_models/
├── cash_flow_forecast/v1.0/
│   ├── metadata.json
│   └── model.pkl
├── goal_feasibility/
│   ├── model-2-phase-b-v1.pkl
│   └── model-2-phase-c-v2.pkl
├── financial_subscription_usage/v1.0/
│   ├── artifact.pkl
│   └── model.pkl
├── financial_shortfall/v1.0/
│   ├── metadata.json
│   └── model.pkl
├── behaviour_engine/v2.0/
│   ├── metadata.json
│   └── model.pkl
├── exposure_forecast/v3.0/
│   ├── metadata.json
│   └── model.pkl
├── financial_anomaly/v2.0/
│   ├── metadata.json
│   └── model.pkl
└── financial_distress/v3.0/
    ├── metadata.json
    └── model.pkl
```
