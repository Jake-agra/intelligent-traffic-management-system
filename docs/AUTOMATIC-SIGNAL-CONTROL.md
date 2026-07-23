# Automatic Signal Control

Phase 13.2 adds safe fixed-time automatic operation for the four-way Raspberry
Pi GPIO intersection. It does not add camera, YOLO, adaptive timing, mobile
features or machine-learning control.

## Modes

- `automatic`: Raspberry Pi runs the local fixed-time cycle and reports each
  confirmed phase.
- `manual`: automatic advancement is paused; authenticated backend manual
  overrides may be sent after the Pi confirms manual mode and all red.
- `failsafe`: critical controller errors attempt all red. Flashing behavior is
  not used in this phase.

## Timing

Defaults:

- `AUTO_NS_GREEN_SECONDS=15`
- `AUTO_NS_YELLOW_SECONDS=3`
- `AUTO_EW_GREEN_SECONDS=15`
- `AUTO_EW_YELLOW_SECONDS=3`
- `AUTO_ALL_RED_SECONDS=2`
- `MANUAL_OVERRIDE_MAX_SECONDS=60`
- `AUTO_CONTROLLER_ENABLED=true`

Shorter timings may be used during bench testing.

## Fixed-Time Sequence

The automatic state machine repeats:

1. `all_red_before_ns`: north/south/east/west red
2. `north_south_green`: north/south green, east/west red
3. `north_south_yellow`: north/south yellow, east/west red
4. `all_red_before_ew`: north/south/east/west red
5. `east_west_green`: east/west green, north/south red
6. `east_west_yellow`: east/west yellow, north/south red

Every phase defines the complete four-direction output state. Conflicting green
phases are rejected.

## Synchronization Flow

```text
Raspberry Pi automatic phase
-> GPIO output change
-> confirmed signal state report
-> backend SignalState and SignalEvent persistence
-> signal.updated WebSocket event
-> dashboard and Digital Twin refresh
```

Controller mode and phase use:

```text
backend mode command
-> MQTT controller-mode command
-> Raspberry Pi ControlModeManager
-> controller/status report
-> backend ControllerState persistence
-> controller.mode_updated WebSocket event
```

The browser never publishes MQTT directly and never predicts unconfirmed
physical signal colour.

## Mode Switching

Automatic to manual:

1. Backend validates admin permission and reason.
2. Backend publishes a typed controller-mode command.
3. Pi publishes `accepted`.
4. Pi cancels automatic advancement.
5. Pi sets all directions red and reports confirmed all red.
6. Pi confirms `manual`.
7. Manual signal controls become available.

Manual to automatic:

1. Pi cancels active manual timers.
2. Pi sets all directions red and reports confirmed all red.
3. Pi confirms `automatic`.
4. Pi restarts from `all_red_before_ns`.

Emergency all red interrupts automatic or manual work, sets every direction red
and requires explicit operator action before automatic mode resumes.

## Reconnection

Automatic operation is edge-autonomous during MQTT outages. GPIO safety does
not depend on network availability. After reconnect, the Pi republishes current
GPIO state and controller mode/phase so the backend and Digital Twin reconcile
to the latest confirmed physical state.

## Manual Physical Synchronization Test

Do not run this automatically.

1. Start Mosquitto:
   `sudo systemctl start mosquitto`
2. Start backend:
   `cd /home/itms/Desktop/intelligent-traffic-management-system/backend`
   `.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Start dashboard:
   `cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard`
   `npm run dev -- --host 0.0.0.0 --port 5173`
4. Start Raspberry Pi service:
   `cd /home/itms/Desktop/intelligent-traffic-management-system/raspberry-pi`
   `. .venv-gpio/bin/activate`
   `python -m app.main`
5. Confirm physical lights initialize all red.
6. Confirm Digital Twin initializes all red.
7. Observe one full automatic cycle:
   north/south green, north/south yellow, all red, east/west green,
   east/west yellow, all red.
8. Verify each physical phase matches the Digital Twin after confirmed updates.
9. Switch to manual mode from dashboard.
10. Confirm automatic cycle stops safely at all red.
11. Send a manual north/south green override.
12. Confirm physical lights and Digital Twin match.
13. Wait for manual duration expiry and confirm all red.
14. Resume automatic mode.
15. Confirm automatic cycle restarts from all red.
16. Test emergency all red.
17. Confirm all four physical modules and the Digital Twin show red.

Correlate backend logs, Raspberry Pi logs and dashboard messages with command
IDs, mode operation IDs and timestamps.

## Limitations

- Fixed-time only; no adaptive timing.
- One four-way intersection controller.
- No flashing failsafe.
- No direct browser MQTT.
- No camera, YOLO, emergency-vehicle detection or mobile features in this phase.
