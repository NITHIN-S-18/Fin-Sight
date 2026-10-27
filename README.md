# FinSight — Financial Exposure Intelligence System

**FinSight** is a full-stack, enterprise-grade personal financial exposure intelligence system designed for individuals and financial planners. It provides explainable visibility into recurring commitments, true exposure risk, cash flow trajectories, and financial goal feasibility through an intuitive dashboard, a non-destructive What-If digital twin simulator, and an AI-powered conversational assistant.

---

## 🌟 Key Features

- **Executive Financial Dashboard**: Real-time visualization of monthly financial capacity, exposure scores, health metrics (0–100), and breakdown of active recurring commitments.
- **Unified Commitment Intelligence**: Automated detection of recurring subscriptions, EMIs, and BNPL obligations with confidence scoring and manual commitment management.
- **Trial Intelligence & Pre-Renewal Alerts**: Automated detection of micro-authorizations and free trials, estimating conversion dates before unexpected charges occur.
- **What-If Digital Twin Simulator**: Interactive non-destructive sandbox allowing users to model financial decisions (new loans, cancellations, income changes, major purchases) and inspect quantified before/after deltas.
- **Production Machine Learning Suite**:
  - **Model 1**: Multi-component Cash Flow & Liquidity Forecast (HistGradientBoosting / XGBoost)
  - **Model 2**: Goal Feasibility Classifier (HistGradientBoosting / Random Forest)
  - **Model 3**: Subscription Usage & Payment Engagement Classifier
  - **Model 4**: Next-Month Financial Shortfall Risk Predictor
  - **Auxiliary Engines**: Anomaly Detection, Distress Classification, Behavioral Persona Clustering
- **AI Financial Assistant (Copilot)**: Context-aware conversational AI assistant capable of answering conceptual financial questions and securely retrieving authenticated personal financial data via structured tool calls.
- **Multi-Tenant Security & Tenant Isolation**: Secure JWT authentication, password hashing, and complete data segregation across user accounts.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, Lucide Icons |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, Uvicorn |
| **Database** | PostgreSQL, Alembic (21 versioned migrations), SQLite fallback (`finsight.db`) |
| **Machine Learning** | Scikit-Learn, XGBoost, Pandas, NumPy, Joblib |
| **Testing** | Pytest, HTTPX, AnyIO (comprehensive automated test suite) |

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ (npm 9+)
- PostgreSQL (or local SQLite for automated tests / zero-configuration development)

---

### 1. Backend Setup

```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install pytest httpx

# Setup environment variables
cp .env.example .env

# Apply database migrations
python -m alembic upgrade head

# Start backend server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The FastAPI backend will be available at `http://127.0.0.1:8000`.
Interactive Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

---

### 2. Frontend Setup

```powershell
# In a new terminal, navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

The React frontend application will be running at `http://localhost:5173`.

---

## 🗄️ Database Migration Management

FinSight uses Alembic for declarative, version-controlled relational schema migrations:

```powershell
# Check current migration revision
python -m alembic current

# Upgrade database to latest revision
python -m alembic upgrade head

# Create a new migration revision after modifying models
python -m alembic revision --autogenerate -m "describe_changes"

# Downgrade by one revision if needed
python -m alembic downgrade -1
```

All 21 migration scripts reside in `backend/alembic/versions/` (versions `001` through `021`).

---

## ⚙️ Production Configuration & Environment Variables

Production deployments supply configuration strictly via environment variables (or `.env` in the backend):

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection URI | `postgresql+psycopg://user:password@host:5432/finsight` |
| `AUTH_JWT_SECRET` | Secret key for signing JWT tokens | 64+ char random hex string |
| `AUTH_JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan | `30` |
| `FRONTEND_BASE_URL` | Frontend origin for CORS and password reset links | `https://finsight.example.com` |
| `EMAIL_DELIVERY_PROVIDER` | Email delivery strategy (`console`, `resend`, `smtp`) | `resend` (prod) / `console` (dev) |
| `RESEND_API_KEY` | Resend API key (if using Resend) | `re_...` |
| `GEMINI_API_KEY` | Google Gemini API key for Copilot assistant | `AIzaSy...` |
| `VITE_API_BASE_URL` | Frontend API base URL | `https://api.finsight.example.com/api/v1` |

---

## 🌐 Important API Entry Points

The backend exposes a versioned REST API under `/api/v1`:

- **Authentication & User Management**: `/api/v1/auth` (register, login, me, export, password reset)
- **Financial Dashboard**: `/api/v1/dashboard` (exposure score, health index, capacity, trends)
- **Transactions & Ingestion**: `/api/v1/transactions` (CSV statement ingestion, transaction list)
- **Recurring Commitments**: `/api/v1/commitments`, `/api/v1/recurring-payments` (EMIs, subscriptions, BNPL)
- **Trial Intelligence**: `/api/v1/trial-intelligence` (detected free trials, pre-renewal alerts)
- **Predictive Forecasts**: `/api/v1/forecast/cash-flow/{user_id}` (Model 1 cash flow projection)
- **Goal Feasibility**: `/api/v1/goals` (Model 2 goal evaluation, monthly savings plan)
- **Shortfall Risk**: `/api/v1/shortfall/{user_id}` (Model 4 next-month liquidity risk)
- **Digital Twin Simulator**: `/api/v1/simulator` (non-destructive scenario evaluation)
- **AI Financial Copilot**: `/api/v1/copilot` (authenticated multi-turn chat with tool calling)

---

## 🧪 Running the Test Suite

```powershell
# From project root:
$env:PYTHONPATH = "backend"
pytest tests/ -v
```

### Frontend Production Build
```powershell
cd frontend
npm run build
```

---

## 📂 Repository Directory Structure

```
finsight-main/
├── backend/
│   ├── alembic/                 # Database migration versions (001 - 021)
│   ├── app/
│   │   ├── api/v1/              # FastAPI router and versioned endpoint handlers
│   │   ├── copilot/             # AI Assistant service, LLM provider, and knowledge tools
│   │   ├── core/                # App configuration, security, JWT auth
│   │   ├── database/            # SQLAlchemy models, connection pool, session factory
│   │   ├── digital_twin/        # Scenario builder for what-if simulations
│   │   ├── ml/                  # 4 production ML models, engines, pipelines
│   │   │   └── saved_models/    # Versioned model artifacts and metadata
│   │   ├── schemas/             # Pydantic request/response models
│   │   └── services/            # Domain business services (Exposure, Commitments, Goals, etc.)
│   ├── research/                # Academic research experiment pipeline and paper artifacts
│   ├── scripts/                 # ML training and evaluation scripts
│   └── requirements.txt         # Production backend dependencies
├── docs/                        # Authoritative technical documentation suite
│   ├── ARCHITECTURE.md          # End-to-end system architecture specification
│   ├── ML_MODELS.md             # Comprehensive ML models specification and metrics
│   ├── API.md                   # Complete REST API reference documentation
│   ├── API_GUIDE.md             # API developer guide and usage patterns
│   ├── DEVELOPMENT.md           # Developer environment, migrations, and contributing guide
│   ├── BUSINESS_RULES.md        # Core financial rules and formulas
│   └── VERIFICATION.md          # Testing and verification methodology
├── frontend/
│   ├── src/
│   │   ├── api/                 # Strongly typed Fetch API client
│   │   ├── app/                 # Main React pages, sidebar, components, and adapters
│   │   └── styles/              # Design system and theme styles
│   └── package.json             # Frontend dependencies and build scripts
├── scripts/                     # Reproducible ML dataset generation and ingestion utilities
├── tests/                       # Automated backend unit, ML, and integration test suite
├── finsight.db                  # Local zero-configuration SQLite development database
└── README.md                    # Canonical project documentation
```

---

## 📖 Documentation Index

- [System Architecture](docs/ARCHITECTURE.md)
- [Machine Learning Models & Metrics](docs/ML_MODELS.md)
- [REST API Reference](docs/API.md)
- [API Developer Guide](docs/API_GUIDE.md)
- [Developer Setup & Contributing](docs/DEVELOPMENT.md)
- [Business Rules & Financial Formulas](docs/BUSINESS_RULES.md)
- [Verification Guide](docs/VERIFICATION.md)

---

## 🎓 Academic Major Project Notice

FinSight was developed as a Final-Year Engineering Major Project demonstrating:
- Scalable, layered micro-monolith enterprise software architecture
- Deterministic financial domain modeling with explainability
- Pragmatic, reproducible machine learning on longitudinal financial data
- Secure multi-tenant authentication and isolated digital twin simulation
