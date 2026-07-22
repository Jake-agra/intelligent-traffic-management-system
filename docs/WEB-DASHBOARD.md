# Web Dashboard

Phase 12 creates the first production-style React + TypeScript operations
dashboard for the Intelligent Traffic Management System.

## Scope

Implemented pages:

- Login
- Overview
- Intersections
- Intersection detail
- Incidents
- Violations
- Alerts
- Devices

Out of scope for Phase 12:

- Mobile application
- 3D simulation
- Camera feeds
- YOLO/computer vision
- Adaptive signal algorithms
- Reports and advanced analytics

## Prerequisites

- Node.js 20+
- npm
- FastAPI backend virtual environment installed
- Backend database configured with users and operational records

## Environment

Create a local dashboard env file from the committed template:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
cp .env.example .env
```

Variables:

- `VITE_API_BASE_URL`: HTTP backend origin, for example `http://127.0.0.1:8000`
- `VITE_WS_BASE_URL`: WebSocket backend origin, for example `ws://127.0.0.1:8000`

Do not commit a real `.env`.

## Install

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm install
```

## Development

Start the backend:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
.venv/bin/python -m uvicorn app.main:app --reload
```

Start the dashboard:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm run dev
```

Local dashboard URL:

```text
http://localhost:5173
```

## Build And Test

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm run typecheck
npm test
npm run build
```

No lint script is configured in Phase 12.

## Authentication Flow

1. Operator submits email and password to `POST /api/v1/auth/login`.
2. Backend returns an access token, refresh token and user profile.
3. The dashboard stores tokens in `sessionStorage`.
4. Authenticated requests use `Authorization: Bearer <access_token>`.
5. A `401` response triggers refresh through `POST /api/v1/auth/refresh`.
6. Logout posts the refresh token to `POST /api/v1/auth/logout` and clears the
   session.
7. Protected routes load the current user through `GET /api/v1/auth/me`.

Roles are read from the backend. Signal controls are visible only to `admin`.

## WebSocket Flow

The dashboard connects to:

```text
WS /api/v1/ws
```

The backend sends `connection.acknowledged`, then domain event envelopes.
Handled events include:

- `traffic.updated`
- `signal.updated`
- `violation.created`
- `incident.created`
- `incident.updated`
- `alert.created`
- `alert.acknowledged`
- `device.status_changed`

The client deduplicates events by `event_id`, sends heartbeat pings, reconnects
with bounded backoff and keeps the latest HTTP data visible while disconnected.

## Signal-Control Flow

The intersection detail page exposes admin-only controls for:

- `POST /api/v1/intersections/{intersection_id}/signal-mode`
- `POST /api/v1/intersections/{intersection_id}/signal-override`

Manual overrides require confirmation and display a visible physical-hardware
warning. The browser never publishes MQTT directly.

Flow:

Web dashboard -> FastAPI authenticated API -> backend validation -> MQTT ->
Raspberry Pi edge service -> GPIO traffic lights.

## Demo Login Procedure

Create or use a backend user with a role that can access the target page. For
local development, seed a demo admin from the backend folder:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
DEMO_ADMIN_PASSWORD='choose-a-local-password' .venv/bin/python -m app.tools.seed_demo
```

- `admin`: full dashboard and signal controls
- `analyst`: overview and read-only intersection pages
- `police`: intersections, alerts and violations
- `emergency_responder`: intersections, alerts and incidents

Then open `http://localhost:5173`, sign in with that email and password, and
confirm the user name appears in the top bar.

The seed command is idempotent and refuses `ENVIRONMENT=production` unless
`--allow-production` is passed deliberately. Do not commit `backend/.env` or
real credentials.

## Testing Signal Override

1. Start the backend.
2. Start the MQTT broker and Raspberry Pi service if testing physical GPIO.
3. Sign in as an `admin`.
4. Open `Intersections`.
5. Select an intersection.
6. In `Signal override`, choose a lane, signal colour, duration and reason.
7. Confirm the hardware warning.
8. Verify the success message includes an operation ID.
9. Watch for `signal.updated` WebSocket refresh on the page.

## Known Limitations

- Phase 12 does not include charts, maps, reports or camera views.
- WebSocket authentication is not enforced by the backend contract yet.
- Overview current signal-state detail is limited by the existing summary
  endpoint; per-intersection signal states are shown on the detail page.
- Signal controls depend on existing backend HTTP endpoints and their current
  validation behavior.

## Backend Test Stability

On the Raspberry Pi Python 3.13 environment, Starlette's threaded in-process
test client path can hang before a request completes. Phase 12.1 keeps backend
pytest deterministic by forcing test settings before app import, disabling MQTT
for tests and using same-process route/realtime tests with fake MQTT and fake
websocket objects.
