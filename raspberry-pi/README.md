# Raspberry Pi Edge Service

Phase 8 adds the hardware-free Raspberry Pi edge-service foundation. It connects
to MQTT when enabled, publishes device heartbeat and telemetry messages, receives
signal commands and sends command acknowledgements.

Phase 9 adds an isolated GPIO driver and manual hardware test for one 4-pin
traffic-light module. MQTT commands are not connected to GPIO yet.

Phase 10 expands the GPIO driver into a configurable four-way intersection
controller for north, south, east and west traffic-light modules. MQTT commands
are still not connected to GPIO.

Phase 11 connects validated MQTT signal commands to the four-way GPIO
intersection controller. The edge service publishes `accepted`, `executed`,
`rejected`, `failed` and `duplicate` acknowledgements as each command moves
through validation and GPIO execution.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DEVICE_ID` and `INTERSECTION_ID` to records known by the backend.

## Run

```powershell
python -m app.main
```

MQTT is disabled by default for development. Set `MQTT_ENABLED=true` and broker
settings in `.env` to connect to a real broker.

MQTT signal command execution requires lane-to-direction mapping in `.env`.
Set each value to the backend lane UUID for the physical direction:

```env
TRAFFIC_LIGHT_NORTH_LANE_ID="backend-north-lane-uuid"
TRAFFIC_LIGHT_SOUTH_LANE_ID="backend-south-lane-uuid"
TRAFFIC_LIGHT_EAST_LANE_ID="backend-east-lane-uuid"
TRAFFIC_LIGHT_WEST_LANE_ID="backend-west-lane-uuid"
SIGNAL_COMMAND_MAX_DURATION_SECONDS="60"
SIGNAL_ALL_RED_TRANSITION_SECONDS="0.2"
```

GPIO is disabled by default in `.env.example`. Copy it to `.env`, then set
`GPIO_ENABLED=true` on a Raspberry Pi only after wiring the traffic-light
modules. The real `.env` file is ignored by git.

Default BCM pins:

| Direction | Red | Yellow | Green |
|---|---:|---:|---:|
| North | 22 | 27 | 17 |
| South | 5 | 6 | 13 |
| East | 19 | 26 | 21 |
| West | 16 | 20 | 12 |

See `../docs/GPIO.md` before wiring.

## Test

```powershell
pytest
```

Manual traffic-light hardware tests:

```powershell
python -m app.intersection_test --direction north
python -m app.intersection_test --direction south
python -m app.intersection_test --direction east
python -m app.intersection_test --direction west
python -m app.intersection_test --sequence
```

## MQTT Topics

- Publishes heartbeat to `itms/v1/devices/{device_id}/heartbeat`
- Publishes device telemetry to `itms/v1/devices/{device_id}/telemetry`
- Subscribes to `itms/v1/intersections/{intersection_id}/commands/signal`
- Publishes acknowledgements to `itms/v1/intersections/{intersection_id}/commands/ack`

## Signal Command Execution

Valid commands are acknowledged as `accepted`, executed through the GPIO
controller, then acknowledged as `executed` after the GPIO operation succeeds.
Timed holds run asynchronously so the MQTT callback path is not blocked by long
durations. When a command expires, the controller returns to all red. A newer
accepted command cancels and replaces the active timed hold.

The service rejects wrong-intersection, stale, malformed, excessive-duration and
unknown-lane commands. Duplicate command IDs are acknowledged as `duplicate`
without re-executing GPIO. GPIO exceptions publish a `failed` acknowledgement.

Startup sets the intersection to all red. Shutdown sets all GPIO outputs off.

## Development Mode

The service runs on Windows, macOS or Linux with `GPIO_ENABLED=false`. In this
mode MQTT commands execute through fake GPIO and still publish acknowledgements.
Raspberry Pi GPIO libraries are imported only when GPIO is enabled. Tests use
fake MQTT and GPIO clients plus static telemetry, while runtime telemetry uses
host metrics where available.
