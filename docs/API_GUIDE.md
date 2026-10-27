# API_GUIDE.md

# FinSight API Guide

## Base URL

/api/v1

---

## Authentication

### POST /auth/register

Creates an authentication account in the separate `auth_users` table.

Request body:

```json
{
	"email": "user@example.com",
	"password": "at-least-8-characters",
	"display_name": "Registered Name"
}
```

Response `201`:

```json
{
	"id": 1,
	"email": "user@example.com",
	"created_at": "2026-09-05T12:00:00",
	"updated_at": "2026-09-05T12:00:00"
}
```

The password and password hash are never returned. Duplicate emails return `409`.

### POST /auth/login

Authenticates an account and returns a JWT.

Request body:

```json
{
	"email": "user@example.com",
	"password": "at-least-8-characters"
}
```

Response `200`:

```json
{
	"access_token": "<jwt>",
	"token_type": "bearer"
}
```

Invalid credentials return `401`.

### GET /auth/me

Returns the current authenticated account. Send the token using:

```text
Authorization: Bearer <jwt>
```

Response `200` uses the same account shape as registration. Missing or invalid tokens return `401`.

### PATCH /auth/me

Updates the authenticated account's display name. The account is selected
from the JWT; no user ID is accepted.

```json
{
  "display_name": "Updated Name"
}
```

### POST /auth/change-password

Changes the authenticated account password after verifying the current
password. Password hashes and credentials are never returned.

```json
{
  "current_password": "current-password",
  "new_password": "new-password"
}
```

### GET /auth/export

Downloads a CSV containing only the authenticated account's persisted
transactions. Reference and other-user data are never included.

Registration also creates a separate empty financial user identity. The
response includes `financial_user_id` and preserves the optional
`display_name`; no training user is assigned. Password recovery is not
currently configured and does not send reset emails.

## Personal transaction ingestion

### POST /transactions/upload

Requires a bearer token and accepts a UTF-8 CSV multipart file. Required
columns are `transaction_date` (ISO date or datetime) and `amount`. Each row
is validated before it is stored for the JWT-linked financial user.

Uploads append to existing transactions. Duplicate protection uses a SHA-256
fingerprint of the authenticated financial user, normalized date, optional
source transaction ID, merchant, description, and amount. The filename is not
used as transaction identity.

Amounts remain signed for general transactions, including legitimate refunds or
credits. Negative subscription, EMI, and BNPL rows are retained as ledger data
but contribute zero to commitment burdens and cannot reduce exposure.

### GET /transactions/imports

Requires a bearer token and returns that account's upload history, including
filename, processing timestamp, transaction date range, accepted count, and
processing status. Financial endpoints reject a path `user_id` that does not
belong to the authenticated account with `403`.

---

## Health

GET /health

Purpose

Check backend availability.

Expected Response

200 OK

---

## Dataset

Global dataset listing and summary routes are not exposed through the
user-facing API. Reference users, transactions, and aggregate dataset
statistics must not be disclosed to ordinary authenticated accounts.

GET /dataset/user/{user_id}

Purpose

Returns a user's financial profile.

Example

U001

---

## Subscription Intelligence

GET /subscriptions/{user_id}

Purpose

Returns subscription intelligence.

Includes

- Active subscriptions
- Monthly cost
- Trial detection
- AutoPay
- Insights

---

## EMI Intelligence

GET /emis/{user_id}

Purpose

Returns EMI intelligence.

Includes

- Active EMIs
- Loan type
- Monthly burden
- Payment analytics
- Insights

---

## BNPL Intelligence

GET /bnpl/{user_id}

Purpose

Returns BNPL intelligence.

Includes

- Active providers
- Installments
- Payment analytics
- Provider concentration
- Insights

---

## Financial Exposure

GET /exposure/{user_id}

Purpose

Returns complete financial exposure report.

Includes

- Exposure Score
- Financial Health
- Commitment Breakdown
- Recommendations
- Forecast
- Explainability

## Generalized Recurring Payments

### GET /recurring-payments

Requires a bearer token and returns both recurring-payment patterns detected
from the authenticated user's persisted transaction ledger and records created
by that user. Detected records have `source: "DETECTED"`; manual records have
`source: "USER_ADDED"`.

Optional query parameters:

- `category`
- `confidence_level` (`high` or `low`)
- `status` (`Active` or `Inactive`)

Low-confidence records are review candidates and do not affect authoritative
exposure or financial-health calculations.

### GET /recurring-payments/{id}

Returns one recurring-payment record owned by the authenticated user.
Cross-user records are not disclosed.

### POST /recurring-payments

Creates a `USER_ADDED` record. The request requires a nonblank name, positive
amount, supported category, supported frequency (`weekly`, `biweekly`,
`monthly`, `quarterly`, or `annual`), and next payment date. Active records
cannot use a past next payment date. Manual records contain no transaction
evidence and do not affect exposure or financial-health calculations.

### PATCH /recurring-payments/{id}

Updates only a `USER_ADDED` record owned by the authenticated user. The
monthly equivalent is recalculated by the backend. Detected records are
read-only through CRUD routes.

### DELETE /recurring-payments/{id}

Soft-deactivates only an owned `USER_ADDED` record, retaining it with
`is_active: false` and `status: "Inactive"`. Inaccessible records return
`404`; no endpoint accepts a client-supplied owner identifier.

## Trial and Authorization Intelligence

### GET /trial-intelligence

Requires authentication and returns tenant-scoped informational alerts for
small successful authorization/verification transactions. States are
`authorization_hold`, `possible_trial`, `possible_conversion`,
`confirmed_recurring`, and `dismissed`. A ₹1 or ₹2 transaction alone remains
an authorization hold and is not treated as a confirmed free trial.

`possible_conversion_date` is nullable. It is populated only when an explicit
trial duration is present in the transaction evidence; no generic 30-day date
is fabricated. `days_until_possible_conversion` is also null when the date is
unavailable.

When a defensible future conversion date exists, the backend records an email
alert schedule approximately two days before it. Resend delivery is backend
only, optional, and failure-tolerant. Missing configuration or delivery
failures leave the alert retryable and never fail transaction ingestion.

### GET /trial-intelligence/{id}

Returns one trial or authorization alert owned by the authenticated user.
Merchant and evidence data from another tenant are never disclosed.

---

## Predictive Intelligence

GET /ml/distress/{user_id}

Purpose

Returns a one-month-ahead failed/declined/rejected transaction-event
prediction. It is not a current financial-risk score and its model
confidence is not a calibrated probability.

---

GET /ml/exposure/{user_id}

Purpose

Returns a one-month-ahead exposure forecast. `forecast_exposure` is distinct
from the authoritative deterministic `current_state.current_exposure`.
The target is successful next-month commitments divided by successful
positive next-month income, multiplied by 100. The response reports target
availability coverage; no-positive-income outcomes are unavailable rather
than assigned a fabricated forecast target.

---

GET /ml/persona/{user_id}

Purpose

Returns the user's current descriptive financial-profile cluster. It is not a
prediction of future behaviour. The response sets `descriptive_only` to true.

---

GET /ml/anomaly/{user_id}

Purpose

Returns a reference-population feature-snapshot anomaly result. It is not
transaction-level anomaly detection or fraud detection. The response
identifies the comparison population and exposes the Isolation Forest
decision score.

The `score` is the Isolation Forest decision function: lower values indicate
more anomalous observations, and it is not a probability. The response
`confidence` field is a heuristic anomaly-strength value, not a calibrated
probability.

---

GET /ml/intelligence/{user_id}

Purpose

Returns the fused predictive intelligence response across all ML engines.

Every intelligence response includes the deterministic `current_state`
(`current_exposure`, `monthly_commitments`, `monthly_capacity`,
`available_capacity`, `financial_health`, and `payment_reliability`). These
are authoritative current values. `model_signals` and `signal_quality`
describe each model separately. The legacy `fused_confidence` field is
retained for compatibility but is only a weighted summary of incomparable
model-specific heuristics; it is not a probability, current-risk score, or
universal AI confidence.

ML endpoints require financial data for the authenticated user. Empty accounts
receive a data-unavailable response rather than fabricated model predictions.

---

POST /simulator/simulate

Requires a bearer token. Accepts only a scenario type and scenario parameters;
the baseline financial state is derived from the JWT-linked financial account.
The scenario is applied to an in-memory Digital Twin and does not modify stored
transactions.

Supported scenario types include:

- `cancel_subscription`
- `add_subscription`
- `new_emi`
- `close_emi`
- `salary_increase`
- `salary_reduction`
- `close_bnpl`
- `add_bnpl`

The response includes baseline and projected health, exposure, commitments,
available capacity, metric deltas, risk interpretation, and recommendation.

---

GET /dashboard/history

Requires a bearer token. Returns one time-series point per observed calendar
month for the authenticated account. Income, spending, and commitments are
aggregated from that user's successful transactions only. Exposure is monthly
commitments divided by monthly income; available capacity is monthly income
less commitments. Financial health is explicitly marked as a transaction-only
exposure approximation and is not copied from a reference profile.

Months without transactions are not fabricated or returned.

---

## Dashboard (Upcoming)

GET /dashboard/{user_id}

Purpose

Returns optimized frontend dashboard response.

Status

Planned

## Financial goal feasibility (Model 2)

### POST /goals/feasibility

Requires a bearer token and evaluates a goal for the authenticated financial
user. The request accepts only `goal_amount` and `timeframe_months`; identity
always comes from the JWT.

The result combines the frozen Model 1 cash-flow forecast with observed
historical variable-spending flexibility. Required saving, adjusted variable
expenses, adjusted net cash, and remaining money are deterministic arithmetic.
Category recommendations use only Model 1's `variable_category_forecast` and
the user's matching successful transaction history. Each recommendation states
its forecast basis, observed monthly spending, supported reduction ceiling,
and remaining savings gap. Protected and committed categories are never
proposed for reduction; absent category forecasts produce no fabricated advice.

The current production decision uses the accepted
`financial_goal_feasibility/model-2-phase-c-v2` classifier as the behavioural
feasibility signal, with the explainable observed-history baseline as a
fallback when the artifact is unavailable. Model 1 forecast values and all
goal arithmetic remain deterministic. No feasibility probability is exposed
because calibration is not part of the product contract. Accounts with fewer
than six months of successful history return
`availability_status: "insufficient_history"` without fabricated values.

### POST /goals

Persists an evaluated goal for the authenticated user and returns the complete
Model 2 result plus the goal identifier. The request requires a nonblank
`goal_name`, `goal_amount`, and `timeframe_months`. Existing records created
before names were persisted return `Savings Goal` as a display-only fallback.

### GET /goals

Returns active goals owned by the authenticated user.

### GET /goals/{id}, PATCH /goals/{id}, DELETE /goals/{id}

Retrieve, update, or soft-deactivate an owned goal. Cross-user goal records
are not disclosed. `PATCH /goals/{id}` accepts an authenticated user's
non-negative `planned_monthly_contribution`. The backend rejects a plan above
the authoritative Model 1 net-cash capacity and returns the remaining amount
after the plan and the remaining goal-saving gap.
# Copilot

`POST /api/v1/copilot/query` and
`GET /api/v1/copilot/suggestions/{user_id}` require authentication. Copilot
derives financial context from the JWT-linked user's transactions and
ExposureService data. The optional request `user_id` is only a compatibility
field and cannot select another financial user.

Accounts without transactions receive an onboarding `404` response instructing
the user to upload transactions before using Copilot. Copilot does not return
fabricated financial metrics when its financial data source is unavailable;
the corresponding domain error is returned instead.

Copilot uses the backend's deterministic explanation when
`COPILOT_LLM_ENABLED=false`. When enabled, `COPILOT_LLM_PROVIDER` supports:

- `auto` (the default): Gemini, then local Ollama, then deterministic fallback
- `gemini`: Gemini only, then deterministic fallback if unavailable
- `ollama`: Ollama only, then deterministic fallback if unavailable
- `deterministic`: deterministic explanation only

Gemini uses `GEMINI_MODEL` (default `gemini-3.8-flash`). Provider failures never
expose secrets and fall back according to the selected mode. The external
provider prompt contains only a compact authenticated-user backend snapshot,
decision factors, recommendation, confidence, and intent; it does not contain
raw transactions, passwords, JWTs, API keys, database credentials, or reference
user rows. External LLM processing is therefore an explicit deployment
configuration choice, not a user-facing privacy or consent guarantee. Teams
enabling Gemini must evaluate the provider's data-handling terms for their
deployment. Exposure, commitment, health, capacity, confidence,
recommendations, and scenario results remain generated by FinSight's
deterministic services. The response metadata identifies the successful
provider or `generated_by=deterministic_fallback`; no fabricated financial
values are used.

## Error responses

Errors use a consistent JSON envelope:

```json
{
  "error": "validation_error",
  "message": "The request payload is invalid.",
  "details": [],
  "path": "/api/v1/example",
  "timestamp": "2026-09-20T12:00:00Z"
}
```

The API uses these status codes:

- `400` for malformed JSON request bodies.
- `401` for missing, invalid, or expired bearer tokens.
- `403` for authenticated users attempting to access another user's data.
- `404` for unknown records or unavailable financial data.
- `409` for duplicate account registration.
- `422` for valid JSON that fails schema or CSV validation.
- `500` for unexpected, database, or intelligence-processing failures.

Unexpected and database failures are logged server-side using safe generic
messages. Internal exception text, credentials, tokens, and database details
are not returned to clients. ML and Copilot failures never produce fabricated
financial predictions or fallback metrics.
## Unified commitments

`GET /api/v1/commitments` returns the authenticated user's canonical current
commitment snapshot. It includes active high-confidence detected records and
active user-added records, monthly-equivalent totals, category/source
breakdowns, eligible items, and exclusion counts. Low-confidence detected
records, inactive records, and trial/authorization records are informational
and are not included in the authoritative total.

## Subscription usage and cancellation intelligence (Model 3)

`GET /api/v1/recurring-payments` returns detected recurring records and
user-added records. Detected subscription records may include
`transactional_engagement_status` (`ACTIVE`, `MODERATE`, or
`UNDER_UTILIZED`) and an explanation based only on payment history. This is
an apparent transactional-engagement signal, not evidence that a user opened,
watched, or used an application. `USER_ADDED` records do not receive ML usage
inference.

`POST /api/v1/recurring-payments/{id}/simulate-cancellation` performs an
in-memory cancellation simulation. It returns current and projected
commitments, expenses, available cash, monthly and annual savings, and
optional goal-feasibility comparisons. No recurring-payment record is changed
and the record must belong to the authenticated user.

## Cash-flow forecast

`GET /api/v1/forecast/cash-flow/{user_id}` requires the JWT-linked financial
user and forecasts the next calendar month's expected income, committed
expenses, variable expenses, total expenses, and net cash. The forecast uses
only observed successful positive transaction amounts and requires six months
of history. Short histories return `forecast_available: false` with
`availability_status: "insufficient_history"`.

The response includes the selected previous-month, three-month-average, or
six-month-average baseline for each component, plus validation metrics and the
chronological split metadata used by the evaluation. Total expenses and net
cash are derived from the predicted components.

Phase 5B training uses separate `HistGradientBoostingRegressor` models for the
three components and fits preprocessing on training rows only. Persisted
artifacts include feature schema, chronological periods, seed, metrics, and
data-cutoff metadata. Expense predictions are non-negative; total expenses and
net cash are derived values. Baseline forecasts remain authoritative for any
target that does not pass the validation acceptance decision.

The current accepted artifact is a hybrid: the reference-data evaluation
accepted HistGradientBoosting only for variable expenses (6.21% validation MAE
improvement over the strongest baseline). Income and committed expenses remain
on their strongest deterministic rolling baselines. When the artifact is
available, the response reports `model_version: "v1.0"`,
`model_type: "accepted-hybrid"`, test-period evaluation metadata, the data
cutoff, and a six-month variable-category forecast. Total expenses and net
cash remain deterministic derivations.
# Model 4 financial shortfall

`GET /api/v1/ml/shortfall/{financial_user_id}` requires the authenticated
user's JWT and returns a categorical next-calendar-month shortfall signal.
The route is tenant-scoped; a user cannot request another financial user's
result. It returns `available: false` with `availability_status:
insufficient_history` when fewer than six historical months are available.

Expected financial values are sourced from the existing Model 1 cash-flow
forecast. Model 4 supplies only the shortfall classification and honest
historical contributing factors. No probability is exposed because the
artifact has not undergone calibration evaluation. If the artifact is
unavailable, the existing deterministic baseline is used.
