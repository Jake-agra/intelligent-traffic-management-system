# Intelligent Traffic Management System

A real-time AIoT traffic management platform aligned with the project documentation. The platform combines a professional web command dashboard, a synchronized mobile application, a FastAPI backend, PostgreSQL, MQTT/WebSockets, Raspberry Pi GPIO control, computer vision, and a 3D traffic simulation.

## Core documented modules

- Vehicle detection and counting
- Traffic density analysis: Low, Medium, High
- Adaptive traffic signal control
- Red-light violation detection
- Accident and abnormal-event detection
- Real-time dashboard and mobile monitoring
- Alerts and notifications
- Historical analytics and reporting
- Raspberry Pi edge processing
- GPIO traffic-light and buzzer control
- Simulated traffic-scenario testing

## Applications

- `backend/` — API, authentication, real-time events, database and MQTT integration
- `web-dashboard/` — responsive Traffic Operations Center
- `mobile-app/` — synchronized live operations and incident-response application
- `simulation/` — 3D digital-twin intersection and traffic scenarios
- `raspberry-pi/` — GPIO, camera, edge detection, MQTT and isolated hardware tests
- `docs/` — architecture, API contracts, hardware maps and documentation traceability

## Real-time synchronization

The web dashboard and mobile app consume the same backend API and WebSocket event stream. Neither client owns traffic state. PostgreSQL stores durable records, while the backend publishes authoritative live state for traffic readings, signal phases, incidents, violations, alerts and device health.

## Engineering principles

- Minimal, purposeful code
- Mobile and web parity for live operational information
- Backend as the single source of truth
- Isolated GPIO testing before hardware integration
- Responsive and accessible interfaces
- Lightweight dependencies and lazy-loaded heavy features
- Documented and testable modules

## MQTT Hardware Signal Test

Phase 11.1 adds a backend developer command for a controlled broker-to-hardware
check of the existing MQTT signal path. Configure backend `.env` with the real
hardware test intersection and lane UUIDs, start the broker, start the backend,
start the Raspberry Pi edge service, then run:

```bash
cd backend
.venv/bin/python -m app.tools.hardware_signal_test --direction north --signal green --duration 5
```

Use the emergency safe-state command if a hardware test needs to return the
prototype intersection to red:

```bash
cd backend
.venv/bin/python -m app.tools.hardware_signal_test --all-red --yes
```

The tool publishes a typed signal command through the backend MQTT service,
waits for matching `accepted` and `executed` acknowledgements, and reports
`RESULT: PASS` or `RESULT: FAIL`. It does not bypass backend MQTT schemas or
publish handcrafted payloads.

## Web Dashboard

Phase 12 adds the first production-style React + TypeScript operations
dashboard in `web-dashboard/`. It connects to the FastAPI backend for
authentication, operational data, WebSocket updates and admin-only signal
controls.

Install and run the dashboard:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm install
npm run dev
```

Start the backend first:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
.venv/bin/python -m uvicorn app.main:app --reload
```

The dashboard uses `VITE_API_BASE_URL` and `VITE_WS_BASE_URL`; copy
`web-dashboard/.env.example` to `web-dashboard/.env` for local overrides.

## Local Backend Demo Seed

For local dashboard login and API testing without PostgreSQL, configure
`backend/.env` to use SQLite and seed a demo admin plus a four-way intersection:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
DEMO_ADMIN_PASSWORD='choose-a-local-password' .venv/bin/python -m app.tools.seed_demo
```

The command does not print the password and can be run repeatedly without
duplicating lanes or signal states. It refuses production by default.

Run the backend from the backend folder:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
.venv/bin/python -m uvicorn app.main:app --reload
```

## Status

Repository foundation initialized. Implementation will proceed in tested phases, beginning with the backend and database foundation.
