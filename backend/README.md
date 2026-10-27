# FinSight Backend

Production-grade FastAPI backend scaffold for FinSight (Financial Exposure Intelligence System).

This repository provides the application architecture, shared infrastructure, and API wiring only. Business logic, persistence, and ML implementations are intentionally left as placeholders.

## Layout

```text
backend/
├── app/
│   ├── api/
│   ├── services/
│   ├── schemas/
│   ├── core/
│   ├── utils/
│   ├── ml/
│   ├── data/
│   └── main.py
├── requirements.txt
└── .env.example
```

## What is included

- FastAPI application factory
- Versioned API routing under `/api/v1`
- Health check endpoint
- Dataset management endpoints backed by CSV files
- CORS configuration
- Environment-based settings
- Centralized logging setup
- Error handling middleware and exception handlers
- Pydantic response schemas
- Clean architecture placeholders for services, data, and ML layers

## Quick start

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Copy environment defaults and adjust as needed:

   ```bash
   copy .env.example .env
   ```

4. Run the API:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Primary endpoint

- `GET /api/v1/health`
- `GET /api/v1/dataset/summary`
- `GET /api/v1/dataset/users`
- `GET /api/v1/dataset/user/{user_id}`
- `GET /api/v1/dataset/transactions`
- `GET /api/v1/dataset/transaction/{transaction_id}`
- `GET /api/v1/dataset/user/{user_id}/transactions`

## Dataset behavior

The dataset layer is loaded once at application startup and then reused through a cached `DatasetService` instance. All future modules should depend on this service instead of reading CSV files directly.

Verification note

- Many verification commands and developer scripts assume the current working directory is the backend folder. Running them from the repository root can produce ModuleNotFoundError because the `app` package lives under the backend directory.

- Recommended workflow for verification and tests:

  1. Change into the backend directory:

     cd backend

  2. Run compile and checks from there (examples):

     python -m compileall app
     python -c "from app.database.connection import engine, SessionLocal; print(engine, SessionLocal)"
     python -m alembic upgrade head
     python -m alembic downgrade -1
     python -m alembic upgrade head
     pytest

- Alternatively, run commands from the repository root with PYTHONPATH set to backend, for example:

  PYTHONPATH=backend python -c "from app.database.connection import engine; print(engine)"

This note aims to reduce confusion when running the DB-01…DB-12 verification checklist and the test suite.

