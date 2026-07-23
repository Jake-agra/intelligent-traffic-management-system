# Web Dashboard

React + TypeScript operations dashboard for the Intelligent Traffic Management
System. Phase 12 connects to the existing FastAPI backend for authentication,
operational data, WebSocket events and admin-only signal controls.

## Setup

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm install
cp .env.example .env
```

Environment variables:

- `VITE_API_BASE_URL`
- `VITE_WS_BASE_URL`

## Development

Start the backend first:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
.venv/bin/python -m uvicorn app.main:app --reload
```

Start the dashboard:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm run dev
```

The local dashboard URL is printed by Vite, normally `http://localhost:5173`.

## Build And Test

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm run typecheck
npm test
npm run build
```

## Backend Dependency

The dashboard expects the FastAPI backend to be running and uses
`VITE_API_BASE_URL` for HTTP requests and `VITE_WS_BASE_URL` for WebSocket
connections.

## Signal Controls

Signal controls are visible only to `admin` users. Manual overrides require
confirmation and call the backend HTTP API; the browser never publishes MQTT
messages directly.

## Digital Twin

The protected route `/intersections/:intersectionId/digital-twin` renders a
live four-way intersection visualization with Three.js. It consumes
the existing live intersection endpoint and shared WebSocket provider. The
scene is visual only; signal control still belongs to the existing backend API
and Raspberry Pi MQTT/GPIO path.
