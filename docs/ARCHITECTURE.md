# System Architecture

## Authoritative data flow

1. The 3D simulation or traffic camera produces traffic observations.
2. Raspberry Pi or the simulation client sends compact telemetry through MQTT or HTTPS.
3. The backend validates, stores and evaluates the telemetry.
4. The signal-control service creates the authoritative phase decision.
5. The backend publishes live WebSocket events.
6. The web dashboard and mobile app update from the same events.
7. The Raspberry Pi receives validated signal commands through MQTT and controls GPIO outputs.

## Shared live features

The web and mobile clients synchronize these resources:

- intersection status
- lane vehicle counts
- Low, Medium and High traffic density
- active signal phase and countdown
- automatic/manual operating mode
- violations and evidence metadata
- accidents and emergency-response status
- alerts and acknowledgements
- Raspberry Pi, camera, MQTT and database health
- historical summaries and reports

## Client responsibilities

### Web dashboard

Provides the full command-centre experience: live monitoring, analytics, configuration, reports, device diagnostics and authorized signal control.

### Mobile application

Provides the same live operational information in a mobile-first layout. It supports alerts, incident response, evidence viewing, intersection monitoring and restricted signal override according to user role.

## Synchronization rule

The clients never synchronize directly with each other. Both subscribe to the backend as the single source of truth. A command made on one client is validated by the backend, persisted where required and broadcast to every connected client.

## MQTT communication foundation

Phase 7 adds the first backend MQTT boundary for future Raspberry Pi controllers.
MQTT is disabled by default in development and tests. When enabled, the backend
subscribes to versioned heartbeat, device telemetry, traffic telemetry and signal
command acknowledgement topics. Incoming messages are validated, stale or
duplicate telemetry is rejected, operational records are persisted and matching
WebSocket events are published through the existing realtime publisher.

Signal command publication is exposed as an internal backend service. API route
handlers do not publish MQTT messages directly, which keeps later MQTT broker
or Redis Pub/Sub replacement isolated from HTTP code.

## Raspberry Pi edge-service foundation

Phase 8 adds `raspberry-pi/` as the first hardware-free edge service. It loads
device and intersection identity from environment configuration, publishes
heartbeat and telemetry messages to MQTT, subscribes to backend signal commands
and publishes command acknowledgements. GPIO, camera and computer-vision
execution remain out of scope for this phase so the service can run on a
developer machine or Raspberry Pi without hardware-specific imports.

## Isolated GPIO intersection control

Phase 10 expands the isolated Raspberry Pi GPIO work into a configurable
four-way intersection controller. The GPIO layer models four traffic-light
modules, one each for north, south, east and west, with fake GPIO support for
tests and real GPIO support only when explicitly enabled. Grouped controller
operations keep north/south green phases separate from east/west green phases
and provide all-red, all-off and cleanup paths for safe hardware testing.

MQTT signal commands are not connected to GPIO in this phase. The edge service
continues to acknowledge MQTT commands without executing hardware changes.

## Document traceability

| Documented requirement | Implementation area |
|---|---|
| Vehicle detection and counting | Raspberry Pi camera/AI service and simulation telemetry |
| Density classification | Backend traffic-analysis service |
| Dynamic signal control | Backend signal engine and Raspberry Pi GPIO controller |
| Red-light violation detection | Tracking service, stop-line rules and violations API |
| Accident detection | Incident-analysis service and alerts |
| Web dashboard | `web-dashboard/` |
| Mobile notifications and live monitoring | `mobile-app/` and notification service |
| Data storage and reports | PostgreSQL and reports API |
| HTTP and MQTT communication | Backend and Raspberry Pi services |
| Simulated traffic scenarios | `simulation/` and automated tests |
