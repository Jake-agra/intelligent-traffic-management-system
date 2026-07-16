# Raspberry Pi Edge Service

Phase 8 adds the hardware-free Raspberry Pi edge-service foundation. It connects
to MQTT when enabled, publishes device heartbeat and telemetry messages, receives
signal commands and sends command acknowledgements. GPIO, camera, YOLO and
simulation code are intentionally not included yet.

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

## Test

```powershell
pytest
```

## MQTT Topics

- Publishes heartbeat to `itms/v1/devices/{device_id}/heartbeat`
- Publishes device telemetry to `itms/v1/devices/{device_id}/telemetry`
- Subscribes to `itms/v1/intersections/{intersection_id}/commands/signal`
- Publishes acknowledgements to `itms/v1/intersections/{intersection_id}/commands/ack`

## Development Mode

The service runs on Windows, macOS or Linux. No GPIO library is imported. Tests
use the fake MQTT client and static telemetry provider, while runtime telemetry
uses host metrics where available.
