# MQTT Contract

Phase 7 defines the initial MQTT foundation between the backend and future
Raspberry Pi controllers. Phase 8 adds the matching Raspberry Pi edge-service
foundation. Phase 11 connects validated Raspberry Pi signal commands to GPIO
execution through the edge service.

## Configuration

MQTT is disabled by default. The backend can start without a broker when
`MQTT_ENABLED=false`.

Required settings when MQTT is enabled:

- `MQTT_BROKER_HOST`
- `MQTT_BROKER_PORT`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`
- `MQTT_TLS_ENABLED`
- `MQTT_CLIENT_ID`
- `MQTT_KEEPALIVE_SECONDS`
- `MQTT_MAX_TELEMETRY_AGE_SECONDS`

Backend hardware integration-test settings:

- `HARDWARE_TEST_INTERSECTION_ID`
- `HARDWARE_TEST_NORTH_LANE_ID`
- `HARDWARE_TEST_SOUTH_LANE_ID`
- `HARDWARE_TEST_EAST_LANE_ID`
- `HARDWARE_TEST_WEST_LANE_ID`

Raspberry Pi edge-service settings:

- `DEVICE_ID`
- `INTERSECTION_ID`
- `SOFTWARE_VERSION`
- `MQTT_ENABLED`
- `MQTT_BROKER_HOST`
- `MQTT_BROKER_PORT`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`
- `MQTT_TLS_ENABLED`
- `MQTT_CLIENT_ID`
- `MQTT_KEEPALIVE_SECONDS`
- `HEARTBEAT_INTERVAL_SECONDS`
- `TELEMETRY_INTERVAL_SECONDS`
- `COMMAND_MAX_AGE_SECONDS`
- `SIGNAL_COMMAND_MAX_DURATION_SECONDS`
- `SIGNAL_ALL_RED_TRANSITION_SECONDS`
- `TRAFFIC_LIGHT_NORTH_LANE_ID`
- `TRAFFIC_LIGHT_SOUTH_LANE_ID`
- `TRAFFIC_LIGHT_EAST_LANE_ID`
- `TRAFFIC_LIGHT_WEST_LANE_ID`
- `AUTO_CONTROLLER_ENABLED`
- `AUTO_NS_GREEN_SECONDS`
- `AUTO_NS_YELLOW_SECONDS`
- `AUTO_EW_GREEN_SECONDS`
- `AUTO_EW_YELLOW_SECONDS`
- `AUTO_ALL_RED_SECONDS`
- `MANUAL_OVERRIDE_MAX_SECONDS`

## Topics

| Direction | Topic |
|---|---|
| Device to backend | `itms/v1/devices/{device_id}/heartbeat` |
| Device to backend | `itms/v1/devices/{device_id}/telemetry` |
| Device to backend | `itms/v1/intersections/{intersection_id}/traffic` |
| Backend to device | `itms/v1/intersections/{intersection_id}/commands/signal` |
| Device to backend | `itms/v1/intersections/{intersection_id}/commands/ack` |
| Backend to device | `itms/v1/intersections/{intersection_id}/commands/controller-mode` |
| Device to backend | `itms/v1/intersections/{intersection_id}/controller/status` |

## Device Heartbeat

```json
{
  "device_id": "uuid",
  "status": "online",
  "cpu_percent": 18.4,
  "memory_percent": 42.1,
  "temperature_c": 51.2,
  "ip_address": "192.168.1.20",
  "software_version": "0.1.0",
  "sent_at": "timezone-aware ISO timestamp"
}
```

The backend validates that the device exists, updates `Device.status` and
`Device.last_seen_at`, records a `DeviceEvent` and publishes
`device.status_changed` when the status changes.

## Device Telemetry

```json
{
  "device_id": "uuid",
  "metrics": {},
  "sent_at": "timezone-aware ISO timestamp"
}
```

The backend validates that the device exists and stores the payload as a
`DeviceEvent`.

## Traffic Telemetry

```json
{
  "intersection_id": "uuid",
  "lane_id": "uuid",
  "vehicle_count": 12,
  "density": "medium",
  "average_speed": 18.5,
  "source": "camera",
  "captured_at": "timezone-aware ISO timestamp"
}
```

The backend validates the intersection and lane relationship, stores a
`TrafficReading` and publishes `traffic.updated`.

## Signal Command

```json
{
  "command_id": "uuid",
  "intersection_id": "uuid",
  "lane_id": "uuid",
  "signal": "green",
  "duration_seconds": 20,
  "reason": "adaptive_density_control",
  "issued_at": "timezone-aware ISO timestamp"
}
```

Signal commands are published through the internal MQTT service, not directly
from API route handlers.

The Raspberry Pi maps `lane_id` to a configured physical direction:

| Setting | Direction |
|---|---|
| `TRAFFIC_LIGHT_NORTH_LANE_ID` | north |
| `TRAFFIC_LIGHT_SOUTH_LANE_ID` | south |
| `TRAFFIC_LIGHT_EAST_LANE_ID` | east |
| `TRAFFIC_LIGHT_WEST_LANE_ID` | west |

The command is rejected if the lane is not mapped, belongs to another
intersection context, is stale, malformed or requests a duration above
`SIGNAL_COMMAND_MAX_DURATION_SECONDS`.

## Signal Command Acknowledgement

```json
{
  "command_id": "uuid",
  "intersection_id": "uuid",
  "lane_id": "uuid",
  "status": "accepted",
  "message": "Command queued",
  "device_id": "uuid",
  "requested_signal": "green",
  "resulting_signals": {
    "north": "green",
    "south": "red",
    "east": "red",
    "west": "red"
  },
  "source": "gpio",
  "acknowledged_at": "timezone-aware ISO timestamp"
}
```

Supported acknowledgement statuses:

- `accepted`
- `executed`
- `rejected`
- `failed`
- `duplicate`

`requested_signal`, `resulting_signals` and `source` are optional for backward
compatibility. They are required for confirmed physical state synchronization.
`resulting_signals` reports application-level direction colours only; it does
not expose raw GPIO pin numbers.

Acknowledgement lifecycle:

1. Valid command received by the Raspberry Pi.
2. Edge service publishes `accepted`; the backend treats this as in progress
   and does not change confirmed current signal state.
3. GPIO safe transition and requested state are applied.
4. Edge service publishes `executed` with `resulting_signals`; the backend
   persists confirmed `SignalState` rows, appends `SignalEvent` history for
   changed lanes and publishes `signal.updated`.
5. Timed hold expires and the edge service returns to all red.
6. Edge service publishes another `executed` report with `source` set to
   `timed_restoration` and all directions red.

If validation fails, the service publishes `rejected`. If the command ID was
already processed, it publishes `duplicate` and does not execute GPIO again. If
GPIO execution fails, it publishes `failed`.

`rejected`, `failed` and `duplicate` acknowledgements do not change confirmed
signal state. Duplicate acknowledgements do not create duplicate `SignalState`
or `SignalEvent` records.

On startup the Raspberry Pi sets GPIO to all red and publishes an `executed`
state report with `source=startup`. After MQTT reconnect it publishes the same
current-state report with `source=reconnect`. The backend validates device and
intersection IDs, rejects stale reports and only appends history when the
reported state differs from the latest confirmed state.

## Controller Mode Command

Phase 13.2 adds explicit controller modes:

- `automatic`
- `manual`
- `failsafe`

Backend mode commands are typed MQTT payloads:

```json
{
  "command_id": "uuid",
  "intersection_id": "uuid",
  "mode": "manual",
  "reason": "operator requested manual control",
  "issued_at": "timezone-aware ISO timestamp"
}
```

The Raspberry Pi validates the intersection and staleness, publishes
`accepted`, serializes any active automatic/manual operation, transitions GPIO
through all red, then publishes `executed` only after the requested mode is
confirmed. Manual signal commands are rejected until manual mode is confirmed.

## Controller Status

```json
{
  "command_id": "uuid",
  "intersection_id": "uuid",
  "status": "executed",
  "mode": "automatic",
  "message": "Automatic phase north_south_green.",
  "device_id": "uuid",
  "phase": "north_south_green",
  "phase_started_at": "timezone-aware ISO timestamp",
  "phase_duration_seconds": 15,
  "next_phase": "north_south_yellow",
  "source": "automatic_phase",
  "acknowledged_at": "timezone-aware ISO timestamp"
}
```

The backend persists one current `ControllerState` per intersection and publishes
`controller.mode_updated`. `accepted` keeps the mode change pending; `executed`
becomes the confirmed mode/phase; `failed` or `rejected` preserve the prior
confirmed mode. GPIO pin numbers are never published.

## Fixed-Time Automatic Cycle

When `AUTO_CONTROLLER_ENABLED=true`, the Pi repeats this local GPIO sequence:

1. `all_red_before_ns`
2. `north_south_green`
3. `north_south_yellow`
4. `all_red_before_ew`
5. `east_west_green`
6. `east_west_yellow`

Every phase defines the complete north/south/east/west output state and is
reported after GPIO execution. The backend and Digital Twin update only from
confirmed reports.

## Hardware Signal Test Tool

Phase 11.1 provides a controlled backend command that exercises the existing
broker-to-hardware path:

Backend command publisher -> MQTT broker -> Raspberry Pi edge service ->
`IntersectionController` -> GPIO traffic lights -> MQTT acknowledgement ->
backend acknowledgement handler.

Prerequisites:

- MQTT broker is running and reachable from both backend and Raspberry Pi.
- Backend `.env` has `MQTT_*` settings plus `HARDWARE_TEST_*` intersection and
  lane UUID mappings.
- Raspberry Pi `.env` has matching `INTERSECTION_ID`,
  `TRAFFIC_LIGHT_*_LANE_ID`, `MQTT_ENABLED=true` and `GPIO_ENABLED=true`.
- Raspberry Pi wiring has already passed one-direction-at-a-time GPIO tests.

Start the broker:

```bash
sudo systemctl start mosquitto
```

Start the backend:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload
```

Start the Raspberry Pi service:

```bash
cd raspberry-pi
. .venv-gpio/bin/activate
python -m app.main
```

Run a north-green hardware test from the backend:

```bash
cd backend
.venv/bin/python -m app.tools.hardware_signal_test --direction north --signal green --duration 5
```

Expected acknowledgement lifecycle:

1. `accepted` for the generated command ID
2. `executed` for the same command ID
3. The tool waits for the command duration while the Pi returns to its safe
   all-red state after expiration
4. `RESULT: PASS`

Emergency all-red command:

```bash
cd backend
.venv/bin/python -m app.tools.hardware_signal_test --all-red --yes
```

The tool uses typed `SignalCommandPayload` messages and
`MQTTService.publish_signal_command()`. It does not publish raw MQTT payloads.
Rejected, failed, duplicate, malformed or timed-out acknowledgements are test
failures.

## Validation Rules

- Timestamps must be timezone-aware.
- Telemetry older than `MQTT_MAX_TELEMETRY_AGE_SECONDS` is rejected.
- Duplicate messages are rejected in-process using payload identity keys.
- Unknown devices, intersections and lane/intersection mismatches are rejected.
- Malformed payloads are logged and do not crash the service.
- Raspberry Pi command execution never permits north/south green at the same
  time as east/west green.
- Right-of-way changes between axes pass through all red for
  `SIGNAL_ALL_RED_TRANSITION_SECONDS`.
