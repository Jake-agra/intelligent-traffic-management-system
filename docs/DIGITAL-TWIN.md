# Digital Twin

Phase 13 adds a live 3D digital twin for one four-way intersection inside the
existing web dashboard.

## Purpose

The digital twin gives operators a compact visual view of the current backend
state for north, south, east and west approaches. It shows traffic-light colour,
aggregate traffic density and bounded illustrative vehicle movement.

The backend remains the single source of truth. The 3D scene never publishes
MQTT commands, never talks to Raspberry Pi GPIO directly and does not maintain
authoritative signal state.

When a physical Raspberry Pi controller is assigned, signal colours represent
the latest confirmed physical state recorded by the backend. Requested and
accepted commands are shown as pending status only. The Digital Twin does not
change authoritative colours until the backend receives an `executed`
acknowledgement or state report from the Raspberry Pi.

Phase 13.2 also displays confirmed controller mode and automatic phase from the
backend live API. Mode changes and phase updates arrive through
`controller.mode_updated` events and trigger a live-state refresh. The scene
does not animate or predict the next phase before physical GPIO confirmation.

## Architecture

Data flow:

```text
FastAPI live endpoint -> dashboard API client -> normalized digital-twin model
FastAPI WebSocket signal.updated -> shared RealtimeProvider -> live endpoint refresh
normalized model -> Three.js scene + textual state panel
```

The implementation separates:

- backend API state
- realtime event state
- normalized digital-twin view model
- 3D rendering components
- animation state

## Backend Data Sources

The page loads:

```text
GET /api/v1/intersections/{intersection_id}/live
```

The live response supplies:

- `intersection`
- `lanes`
- `current_signal_states`
- `latest_traffic_readings`
- `devices`
- `generated_at`

## WebSocket Events Used

The page reuses the dashboard's existing `RealtimeProvider`; it does not open a
second socket. Relevant events for the selected intersection trigger a fresh
live endpoint read:

- `signal.updated`
- `traffic.updated`
- `device.status_changed`
- `controller.mode_updated`
- `incident.created`
- `incident.updated`

Duplicate event IDs are ignored before refresh.

`signal.updated` may include command status. `accepted` means pending physical
execution; `rejected` and `failed` are displayed without changing the confirmed
signal state. `executed` means the backend has persisted the confirmed physical
state and the refreshed live API should match the GPIO modules.

`controller.mode_updated` may include `automatic`, `manual` or `failsafe`, the
current phase, phase start timestamp, duration and next phase. The page displays
pending mode changes separately from confirmed physical signal colours.

## Signal Mapping

The digital twin maps `lanes[].direction` to:

- `north`
- `south`
- `east`
- `west`

Signal states are joined by `lane_id`. The scene displays:

- red
- yellow
- green
- unknown

Missing lanes, missing signal states, unsupported signal values and stale data
are shown as unknown rather than invented.

If historical signal rows contain duplicates for the same lane, the API and UI
select one latest authoritative state per lane. `started_at` is ordered first,
with the signal-state UUID used as a deterministic tie-breaker.

## Traffic-Density Visualization

Traffic readings are joined by `lane_id`. Vehicle visuals are derived from
aggregate `vehicle_count` and `density`, then capped to protect browser
performance.

When no traffic reading exists for a direction, the scene still renders the
road, labels and traffic-light structures. The status panel shows `No traffic
data`, the text count is zero and the 3D scene shows zero vehicles. The browser
does not generate random production traffic.

The vehicles are illustrative. They are not real tracked vehicle positions
unless a future backend explicitly supplies tracked positions.

## Vehicle Behavior

Vehicles move along deterministic lane paths:

- green: proceed through the intersection
- yellow: stop before the stop line unless already crossing
- red or unknown: stop before the signal unless already crossing

The animation uses frame-time deltas and does not affect backend control logic.

## Development Commands

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

Open:

```text
http://localhost:5173/intersections/<intersection-id>/digital-twin
```

For local demo vehicles, seed optional traffic readings explicitly:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
DEMO_ADMIN_PASSWORD='choose-a-local-password' .venv/bin/python -m app.tools.seed_demo --with-traffic
```

The demo readings are idempotent and are not created at backend startup.

## Raspberry Pi Display Layout

On desktop-sized Raspberry Pi displays around `1366x768`, the page uses a
compact two-column layout: the 3D canvas remains in the left column with an
approximately `480-540px` height, while the status panel scrolls independently
on the right. Smaller screens keep the mobile stacked layout.

## Test And Build Commands

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm run typecheck
npm test
npm run build
```

No lint script exists in Phase 13.

## Performance Limits

- Low-cost procedural geometry only
- No downloaded 3D assets
- No external textures
- No post-processing
- Simple lighting
- Vehicle count capped at 10 per direction
- Three.js animation state stays inside renderer-local refs where practical

## Accessibility

The 3D canvas is paired with a semantic textual state panel showing direction,
signal, lane mapping, density, vehicle count, connection state and last update
time. If WebGL initialization fails, the textual panel remains available.

## Phase 13 Limitations

- One intersection at a time
- No city map, buildings, terrain, pedestrians or weather
- No collision physics
- No camera, YOLO or adaptive control
- No MQTT publishing from the browser
- Vehicles represent aggregate traffic density, not measured tracks
