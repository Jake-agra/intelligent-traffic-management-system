# Real-Time Contract

The backend is the authoritative source for both the web dashboard and mobile application.

## Initial WebSocket events

- `traffic.updated`
- `signal.updated`
- `violation.created`
- `incident.created`
- `incident.updated`
- `alert.created`
- `alert.acknowledged`
- `device.status_changed`

## Event envelope

Every event includes:

- event identifier
- event type
- server timestamp
- intersection identifier when applicable
- schema version
- validated payload

## Synchronization guarantees

- Web and mobile receive the same authoritative event payload.
- Commands are validated and persisted before broadcast where required.
- Clients reconnect and refresh current state after losing a connection.
- Event versions prevent stale updates from replacing newer state.
- Role permissions apply equally to web and mobile commands.

This contract prevents the web dashboard and mobile app from displaying conflicting traffic, signal, alert, incident or device information.
