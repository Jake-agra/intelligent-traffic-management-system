# Raspberry Pi Edge Service

Phase 8 adds the hardware-free Raspberry Pi edge-service foundation. It connects
to MQTT when enabled, publishes device heartbeat and telemetry messages, receives
signal commands and sends command acknowledgements.

Phase 9 adds an isolated GPIO driver and manual hardware test for one 4-pin
traffic-light module. MQTT commands are not connected to GPIO yet.

Phase 10 expands the GPIO driver into a configurable four-way intersection
controller for north, south, east and west traffic-light modules. MQTT commands
are still not connected to GPIO.

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

## Development Mode

The service runs on Windows, macOS or Linux with `GPIO_ENABLED=false`. Raspberry
Pi GPIO libraries are imported only when GPIO is enabled. Tests use fake MQTT and
GPIO clients plus static telemetry, while runtime telemetry uses host metrics
where available.
