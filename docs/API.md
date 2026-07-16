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

## Phase 5 Authentication

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Authentication uses email/password login, short-lived JWT bearer access tokens
and rotating refresh tokens. Refresh tokens are stored only as hashes and are
revoked when rotated or logged out.

## Access Matrix

| Resource | Roles |
|---|---|
| `GET /api/health` | Public |
| `GET /api/v1/intersections` | `admin`, `police`, `analyst`, `emergency_responder` |
| `GET /api/v1/intersections/{intersection_id}` | `admin`, `police`, `analyst`, `emergency_responder` |
| `GET /api/v1/intersections/{intersection_id}/live` | `admin`, `police`, `analyst`, `emergency_responder` |
| `GET /api/v1/alerts` | `admin`, `police`, `analyst`, `emergency_responder` |
| `GET /api/v1/violations` | `admin`, `police` |
| `GET /api/v1/incidents` | `admin`, `emergency_responder` |
| `GET /api/v1/devices` | `admin` |
| `GET /api/v1/dashboard/summary` | `admin`, `analyst` |
