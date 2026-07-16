# API

The backend is the authoritative API for both the web dashboard and mobile application.

## Phase 3 Read-Only Traffic Operations

- `GET /api/v1/intersections`
- `GET /api/v1/intersections/{intersection_id}`
- `GET /api/v1/intersections/{intersection_id}/live`
- `GET /api/v1/incidents`
- `GET /api/v1/violations`
- `GET /api/v1/alerts`
- `GET /api/v1/devices`
- `GET /api/v1/dashboard/summary`

Paginated endpoints return `items`, `total`, `limit`, and `offset`. Incidents,
alerts, violations, and devices support filtering by intersection where applicable;
incidents, alerts, and devices also support status filtering.
