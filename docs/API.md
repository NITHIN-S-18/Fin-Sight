# FinSight — REST API Reference (v1)

This document specifies the REST API endpoints provided by the FinSight FastAPI backend (`/api/v1`).

All protected endpoints require an `Authorization` header containing a valid JSON Web Token (JWT):
```http
Authorization: Bearer <access_token>
```

---

## 1. Authentication & Profile (`/api/v1/auth`)

### `POST /api/v1/auth/register`
Creates a new authenticated user account and initializes an empty isolated ledger.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123",
    "display_name": "Nithin"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "auth_user_id": 1,
    "user_id": "AUTH00000001",
    "email": "user@example.com",
    "display_name": "Nithin"
  }
  ```

### `POST /api/v1/auth/login`
Authenticates user credentials and issues a bearer access token.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "auth_user_id": 1,
      "user_id": "AUTH00000001",
      "email": "user@example.com",
      "display_name": "Nithin",
      "avatar_url": null
    }
  }
  ```

### `GET /api/v1/auth/me` *(Protected)*
Returns the current authenticated user session details.

### `PATCH /api/v1/auth/profile` *(Protected)*
Updates display name or password.

### `POST /api/v1/auth/avatar` *(Protected)*
Uploads a user avatar image (`image/png`, `image/jpeg`, `image/webp`).

---

## 2. Dashboard & Exposure Engine (`/api/v1/dashboard`, `/api/v1/exposure`)

### `GET /api/v1/dashboard/{user_id}` *(Protected)*
Retrieves the comprehensive dashboard overview for the user.
- **Response `200 OK`**:
  - `user_profile`: Persona, age group, income category
  - `current_financial_status`: Monthly capacity, total commitments, exposure score, available capacity
  - `financial_health`: Health score (0–100), health label, factor breakdown
  - `breakdown`: Subscriptions, EMIs, BNPL obligations
  - `recommendations`: Prioritized actionable financial advice
  - `forecast`: Next-month and 6-month projected exposure trajectories

### `GET /api/v1/exposure/{user_id}` *(Protected)*
Returns full exposure analytics, including sensitivity bounds, concentration analysis, and risk factors.

---

## 3. Commitments & Recurring Obligations (`/api/v1/commitments`, `/api/v1/recurring-payments`)

### `GET /api/v1/commitments` *(Protected)*
Returns the canonical snapshot of all active recurring commitments from `UnifiedCommitmentService`.
- **Response `200 OK`**:
  ```json
  {
    "total_monthly_commitments": 1499.00,
    "active_commitment_count": 3,
    "breakdown_by_category": {
      "subscription": 499.00,
      "emi": 1000.00
    },
    "breakdown_by_source": {
      "DETECTED": 499.00,
      "USER_ADDED": 1000.00
    },
    "commitment_items": [ ... ]
  }
  ```

### `GET /api/v1/recurring-payments` *(Protected)*
Lists all persisted recurring payments with detection confidence, schedule dates, and payment history.

### `POST /api/v1/recurring-payments` *(Protected)*
Creates a manual (`USER_ADDED`) recurring payment obligation.

### `PATCH /api/v1/recurring-payments/{id}` *(Protected)*
Updates status (Active/Paused/Cancelled), amount, or frequency of a recurring payment.

### `POST /api/v1/recurring-payments/{id}/simulate-cancellation` *(Protected)*
Simulates the financial impact of cancelling a recurring payment without modifying actual records.

---

## 4. Trial Intelligence (`/api/v1/trial-intelligence`)

### `GET /api/v1/trial-intelligence` *(Protected)*
Lists all detected free-trial and micro-authorization charges ($1/$2 verification holds).
- **Response Fields**:
  - `merchant_name`: Merchant initiating trial
  - `detected_state`: `possible_trial`, `possible_conversion`, `confirmed_recurring`
  - `possible_conversion_date`: Estimated date trial expires and first full payment occurs
  - `days_until_possible_conversion`: Days remaining before auto-conversion

---

## 5. Financial Goals & Feasibility (`/api/v1/goals`)

### `GET /api/v1/goals` *(Protected)*
Returns all active financial savings goals for the authenticated user.

### `POST /api/v1/goals` *(Protected)*
Creates a new savings goal with target date and automatically calculates required monthly savings.

### `GET /api/v1/goals/{id}/feasibility` *(Protected)*
Evaluates goal feasibility using Model 2 (HistGradientBoosting / Random Forest) against available capacity.

---

## 6. What-If Digital Twin Simulator (`/api/v1/simulator`)

### `POST /api/v1/simulator/simulate` *(Protected)*
Runs a non-destructive simulation on the user's digital financial twin.
- **Request Body**:
  ```json
  {
    "user_id": "AUTH00000001",
    "scenarios": [
      {
        "scenario_type": "add_subscription",
        "parameters": {
          "name": "Cloud Storage",
          "amount": 299.00,
          "frequency": "Monthly",
          "commitment_type": "Optional"
        }
      }
    ]
  }
  ```
- **Response `200 OK`**:
  - `baseline_state`: Pre-simulation exposure, commitments, health score
  - `simulated_state`: Post-simulation state
  - `deltas`: Exposure delta, monthly cash flow change, health score impact
  - `summary_message`: Human-readable explanation of simulation consequences

---

## 7. AI Assistant / Copilot (`/api/v1/copilot`)

### `POST /api/v1/copilot/query` *(Protected)*
Submits a query to the AI Assistant. The Assistant detects intent, securely fetches authenticated personal financial context via tools, and generates a structured response.
- **Request Body**:
  ```json
  {
    "query": "What is my total monthly commitment right now?",
    "conversation_id": "conv_12345"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "answer": "Your total monthly commitment is \u20b91,499.00 across 3 active obligations...",
    "conversation_id": "conv_12345",
    "intent": "financial_query",
    "tools_used": ["get_user_commitments"],
    "confidence": 0.95
  }
  ```

### `GET /api/v1/copilot/conversations` *(Protected)*
Lists conversation history for the authenticated user.

---

## 8. Transactions & Data Ledger (`/api/v1/transactions`, `/api/v1/dataset`)

### `POST /api/v1/transactions/upload` *(Protected)*
Ingests a CSV transaction ledger. Automatically deduplicates rows, normalizes merchant names and classes, and synchronizes the user's financial profile.
- **File Format**: Standard CSV with headers `transaction_date`, `amount`, `merchant_name`, `description`, `transaction_status`.

### `GET /api/v1/transactions/imports` *(Protected)*
Lists all uploaded CSV batches, timestamps, total rows, and duplicate row counts.

### `GET /api/v1/dataset/user/{user_id}/transactions` *(Protected)*
Fetches all ledger transactions for the authenticated user.

---

## 9. Machine Learning Endpoints (`/api/v1/ml`)

- `GET /api/v1/ml/intelligence/{user_id}`: Comprehensive fused ML intelligence bundle (distress, forecast, persona, anomaly)
- `GET /api/v1/ml/distress/{user_id}`: Financial distress risk score and classification
- `GET /api/v1/ml/exposure/{user_id}`: Machine learning exposure forecast
- `GET /api/v1/ml/persona/{user_id}`: Behavioral persona clustering
- `GET /api/v1/ml/anomaly/{user_id}`: Transactional anomaly detection
- `GET /api/v1/ml/shortfall/{user_id}`: Model 4 next-month cash shortfall risk
- `GET /api/v1/ml/forecast/cashflow/{user_id}`: Model 1 multi-component cash flow forecast
