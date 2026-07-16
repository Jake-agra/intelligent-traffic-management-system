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

These endpoints require bearer-token authentication according to the access
matrix in `docs/API.md`.

## Authentication API

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

The backend uses Argon2 password hashing, short-lived JWT access tokens and
rotating refresh tokens. Configure token settings in `.env`.

## Operational Actions

Phase 6 adds authenticated operational actions for alert acknowledgement,
incident workflow updates and signal-mode or signal-override requests. Successful
actions create audit history and publish realtime events. Signal overrides update
backend state only; no GPIO or device-control execution is included yet.

## MQTT Foundation

Phase 7 adds a lightweight MQTT service boundary for future Raspberry Pi
controllers. MQTT is disabled by default and configured with `MQTT_*`
environment variables. When enabled, a Paho MQTT adapter connects to the
configured broker. The service validates heartbeat, device telemetry, traffic
telemetry and signal command acknowledgement payloads, persists the resulting
operational records and publishes synchronized WebSocket events.

Signal commands are published through the internal MQTT service. API routes
should not publish MQTT messages directly.

## Real-Time Events

Phase 4 adds the shared WebSocket stream for future web and mobile clients:

- `WS /api/v1/ws`

Clients receive a connection acknowledgement after subscribing. Optional query
filters are supported with `intersection_id=<uuid>` and
`events=traffic.updated,signal.updated`.
