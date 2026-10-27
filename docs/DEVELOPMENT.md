# FinSight — Developer & Contributor Guide

This guide covers local development environment setup, running tests, database migrations, model training, and codebase conventions for **FinSight**.

---

## 1. Prerequisites

- **Python**: 3.11 or 3.12 (64-bit)
- **Node.js**: 18+ (with npm 9+)
- **PostgreSQL**: 14+ (or SQLite fallback for offline test suites)
- **PowerShell / Bash**: Standard terminal environment

---

## 2. Local Setup Instructions

### Backend Setup

1. **Navigate to the repository and activate virtual environment**:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies**:
   ```powershell
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -r requirements.txt
   python -m pip install pytest httpx2
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` in `backend/`:
   ```powershell
   cp .env.example .env
   ```
   Ensure `DATABASE_URL` is configured for your PostgreSQL instance (e.g. `postgresql://<username>:<password>@localhost:5432/<database>`).

4. **Apply Database Migrations**:
   ```powershell
   python -m alembic upgrade head
   ```

5. **Start the FastAPI Development Server**:
   ```powershell
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   The API will be available at `http://127.0.0.1:8000` with interactive docs at `http://127.0.0.1:8000/docs`.

---

### Frontend Setup

1. **Navigate to the frontend directory**:
   ```powershell
   cd frontend
   ```

2. **Install dependencies**:
   ```powershell
   npm install
   ```

3. **Start the Vite development server**:
   ```powershell
   npm run dev
   ```
   The UI will be available at `http://localhost:5173`.

4. **Run a production build**:
   ```powershell
   npm run build
   ```

---

## 3. Running the Test Suite

The test suite contains 175 comprehensive tests covering authentication, tenant isolation, financial services, CSV ingestion, ML models, What-If simulator, and API contracts.

### Running all backend tests
Run from the repository root:
```powershell
$env:PYTHONPATH = "backend"
pytest tests/ -v
```

### Running specific test modules
- Multi-user isolation & ledger integrity:
  ```powershell
  pytest tests/test_multi_user_financial_data.py -v
  ```
- Commitments & recurring payment intelligence:
  ```powershell
  pytest tests/test_commitment_phase4.py tests/test_recurring_payment_service.py -v
  ```
- Machine learning models & quality gates:
  ```powershell
  pytest tests/test_ml_quality.py tests/test_shortfall_model4.py tests/test_subscription_usage_model3.py -v
  ```
- What-If simulator & digital twin:
  ```powershell
  pytest tests/test_simulator_api.py -v
  ```

---

## 4. Database Migrations (Alembic)

When modifying database models in `backend/app/database/models/`:

1. Create a new migration script:
   ```powershell
   cd backend
   python -m alembic revision -m "description_of_change"
   ```
2. Inspect the generated file in `backend/alembic/versions/` and implement `upgrade()` and `downgrade()`.
3. Apply migration:
   ```powershell
   python -m alembic upgrade head
   ```

---

## 5. Machine Learning Training Scripts

All ML models can be retrained reproducibly using scripts in `backend/scripts/`:

- **Generate synthetic longitudinal reference dataset**:
  ```powershell
  python scripts/generate_ml_dataset.py --output-dir backend/app/data/ml_dataset_v3
  ```
- **Train Model 1 (Cash Flow Forecast)**:
  ```powershell
  python backend/scripts/train_cashflow_forecast.py
  ```
- **Train Model 2 (Goal Feasibility)**:
  ```powershell
  python backend/scripts/train_goal_feasibility.py
  ```
- **Train Model 3 (Subscription Usage)**:
  ```powershell
  python backend/scripts/train_subscription_usage.py
  ```
- **Train Model 4 (Shortfall Prediction)**:
  ```powershell
  python backend/scripts/train_shortfall.py
  ```

---

## 6. Code Style & Architectural Conventions

- **Services over Endpoints**: Endpoints in `app/api/v1/endpoints/` only handle input validation, authentication, and HTTP responses. Business logic belongs strictly in `app/services/`.
- **Deterministic Arithmetic**: Never replace deterministic service calculations with statistical ML predictions.
- **Tenant Isolation**: Always resolve personal user context through the authenticated JWT session (`current_user.user_id`). Never allow client-provided `user_id` query params to bypass authentication.
- **Strict Typing**: All schemas use Pydantic models with `ConfigDict(from_attributes=True)`.
