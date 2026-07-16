# Backend

Minimal backend foundation for the Intelligent Traffic Management System.

## Stack

- Python
- FastAPI
- Pydantic Settings
- SQLAlchemy
- PostgreSQL
- Pytest

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `.env` with the PostgreSQL connection string for your local environment.

## Run

```powershell
uvicorn app.main:app --reload
```

## Test

```powershell
pytest
```

## Migrations

```powershell
alembic upgrade head
```

Create new migrations after model changes:

```powershell
alembic revision --autogenerate -m "describe change"
```

## Health Check

`GET /api/health` returns service metadata, API status, and database connectivity status.

## Traffic Operations API

Phase 3 adds read-only shared endpoints for the web dashboard and mobile application:

- `GET /api/v1/intersections`
- `GET /api/v1/intersections/{intersection_id}`
- `GET /api/v1/intersections/{intersection_id}/live`
- `GET /api/v1/incidents`
- `GET /api/v1/violations`
- `GET /api/v1/alerts`
- `GET /api/v1/devices`
- `GET /api/v1/dashboard/summary`
