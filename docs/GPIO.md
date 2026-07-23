# Raspberry Pi GPIO Intersection

Phase 10 provides isolated manual GPIO control for four 4-pin traffic-light
modules. Phase 11 connects validated MQTT signal commands to the same
four-way controller.

## Module Pins

Each traffic-light module has four pins:

- `G`
- `Y`
- `R`
- `GND`

## Default BCM Mapping

| Direction | Module `R` | Module `Y` | Module `G` |
|---|---:|---:|---:|
| North | BCM `22` | BCM `27` | BCM `17` |
| South | BCM `5` | BCM `6` | BCM `13` |
| East | BCM `19` | BCM `26` | BCM `21` |
| West | BCM `16` | BCM `20` | BCM `12` |

These defaults can be changed in `raspberry-pi/.env` with:

- `TRAFFIC_LIGHT_NORTH_RED_PIN`
- `TRAFFIC_LIGHT_NORTH_YELLOW_PIN`
- `TRAFFIC_LIGHT_NORTH_GREEN_PIN`
- `TRAFFIC_LIGHT_SOUTH_RED_PIN`
- `TRAFFIC_LIGHT_SOUTH_YELLOW_PIN`
- `TRAFFIC_LIGHT_SOUTH_GREEN_PIN`
- `TRAFFIC_LIGHT_EAST_RED_PIN`
- `TRAFFIC_LIGHT_EAST_YELLOW_PIN`
- `TRAFFIC_LIGHT_EAST_GREEN_PIN`
- `TRAFFIC_LIGHT_WEST_RED_PIN`
- `TRAFFIC_LIGHT_WEST_YELLOW_PIN`
- `TRAFFIC_LIGHT_WEST_GREEN_PIN`

Verify that no GPIO pin is duplicated before running with `GPIO_ENABLED=true`.
The controller rejects duplicate BCM pins during setup.

## Physical Wiring

Power off the Raspberry Pi before wiring or changing any connection.

| Direction | Module label | Connect to Raspberry Pi | Physical header pin |
|---|---|---|---:|
| North | `R` | BCM `GPIO 22` | 15 |
| North | `Y` | BCM `GPIO 27` | 13 |
| North | `G` | BCM `GPIO 17` | 11 |
| South | `R` | BCM `GPIO 5` | 29 |
| South | `Y` | BCM `GPIO 6` | 31 |
| South | `G` | BCM `GPIO 13` | 33 |
| East | `R` | BCM `GPIO 19` | 35 |
| East | `Y` | BCM `GPIO 26` | 37 |
| East | `G` | BCM `GPIO 21` | 40 |
| West | `R` | BCM `GPIO 16` | 36 |
| West | `Y` | BCM `GPIO 20` | 38 |
| West | `G` | BCM `GPIO 12` | 32 |
| All | `GND` | Ground | Any Pi ground pin |

All four module `GND` pins must connect to Raspberry Pi ground. A breadboard
ground rail can make this cleaner: connect one Pi ground pin to the rail, then
connect every module `GND` pin to the same rail.

## BCM Versus Physical Pins

The driver uses BCM numbering. BCM numbers are the GPIO channel numbers used by
the Broadcom chip, not the physical header pin positions. For example, BCM
`GPIO 17` is physical header pin `11`.

When changing configuration, set `TRAFFIC_LIGHT_*_PIN` values to BCM GPIO
numbers, not physical header pin numbers.

## Safe Mounting Order

1. Power off the Raspberry Pi.
2. Mount the modules securely before connecting signal wires.
3. Connect all module `GND` pins to a shared Pi ground.
4. Wire one module at a time using the table above.
5. Verify no configured BCM pin is duplicated.
6. Run one direction test before wiring or testing the next direction.
7. Run the grouped sequence only after all four direction tests pass.

## Voltage Warning

Raspberry Pi GPIO pins are 3.3 V logic pins. Do not connect 5 V signal voltage
to a GPIO pin. Confirm that each traffic-light module is compatible with 3.3 V
GPIO control or use suitable level shifting or driver circuitry.

## Manual Direction Tests

From the `raspberry-pi/` directory:

```bash
python -m app.intersection_test --direction north
python -m app.intersection_test --direction south
python -m app.intersection_test --direction east
python -m app.intersection_test --direction west
```

Each direction test prints the selected direction and BCM pin mapping, then runs:

1. Red for 2 seconds
2. Yellow for 1 second
3. Green for 2 seconds
4. Red for 2 seconds
5. All outputs off
6. Cleanup

Use one-module-at-a-time testing while wiring the prototype. This makes crossed
wires and incorrect module labels much easier to spot.

## Grouped Sequence Test

From the `raspberry-pi/` directory:

```bash
python -m app.intersection_test --sequence
```

Expected grouped sequence:

1. All red
2. North/south green while east/west stay red
3. North/south yellow
4. All red
5. East/west green while north/south stay red
6. East/west yellow
7. All red
8. All off
9. Cleanup

Durations can be adjusted with command-line flags such as:

```bash
python -m app.intersection_test --sequence --green-seconds 3 --yellow-seconds 2
```

## Troubleshooting

- If the command prints `GPIO enabled: False`, set `GPIO_ENABLED=true` in
  `raspberry-pi/.env`.
- If running away from a Raspberry Pi, leave `GPIO_ENABLED=false`; the command
  will print steps without importing Raspberry Pi GPIO libraries.
- If using a virtual environment on the Pi, confirm it can import `RPi.GPIO`, or
  run the manual test with system Python.
- If one colour is wrong, check that module labels `G`, `Y` and `R` match the
  BCM settings.
- If several modules behave strangely, recheck the shared ground rail.
- If setup fails with a duplicate-pin error, fix the repeated
  `TRAFFIC_LIGHT_*_PIN` value before running hardware tests.
- If the Pi restarts or behaves unexpectedly, power it off and recheck ground,
  voltage compatibility and any current-limiting requirements for the modules.

## MQTT Command Execution

The Raspberry Pi edge service maps backend lane UUIDs to physical directions
with these `.env` settings:

| Setting | Physical direction |
|---|---|
| `TRAFFIC_LIGHT_NORTH_LANE_ID` | north |
| `TRAFFIC_LIGHT_SOUTH_LANE_ID` | south |
| `TRAFFIC_LIGHT_EAST_LANE_ID` | east |
| `TRAFFIC_LIGHT_WEST_LANE_ID` | west |

Do not hard-code database UUIDs in application code. Keep the mapping in the
real `raspberry-pi/.env` file.

Command flow:

1. MQTT command arrives on `itms/v1/intersections/{intersection_id}/commands/signal`.
2. The edge service validates intersection, lane mapping, signal colour,
   staleness, duplicate command ID and duration limit.
3. Valid commands publish `accepted`.
4. GPIO executes through `IntersectionController`.
5. Successful GPIO execution publishes `executed` with the full
   north/south/east/west physical state.
6. The command holds for `duration_seconds` asynchronously.
7. Expiration returns the intersection to all red and publishes another
   `executed` state report with `source=timed_restoration`.

Right-of-way changes between north/south and east/west pass through all red for
`SIGNAL_ALL_RED_TRANSITION_SECONDS`. Duplicate command IDs publish `duplicate`
and do not run GPIO again. GPIO exceptions publish `failed`.

Startup safe state is all red and is reported to the backend after MQTT
connect. MQTT reconnect also reports the current physical state. Shutdown safe
state is all outputs off; this is treated as a hardware/offline safety state,
not as a green or red right-of-way.

The current executor applies the requested lane module plus safe opposite-axis
red modules. It does not invent a paired green for the same axis unless the GPIO
controller actually applies that grouped phase. The backend records the
reported physical state, not merely the originally requested lane.

## Automatic Fixed-Time Control

Phase 13.2 adds local Raspberry Pi automatic GPIO control. With
`AUTO_CONTROLLER_ENABLED=true`, the edge service initializes all four modules to
red, publishes confirmed startup state, then repeats:

1. `all_red_before_ns`
2. north/south green, east/west red
3. north/south yellow, east/west red
4. `all_red_before_ew`
5. east/west green, north/south red
6. east/west yellow, north/south red

The Pi publishes a full confirmed physical state after each phase. The backend
persists that state and the Digital Twin refreshes from backend-confirmed data.
If MQTT disconnects, GPIO cycling continues locally; on reconnect the Pi
publishes current GPIO state and controller mode/phase.

Manual mode pauses automatic advancement, confirms all red, and then accepts
bounded manual signal commands. Manual command expiry returns to all red and
stays in manual mode until an operator resumes automatic mode. Emergency all
red interrupts automatic or manual control and requires an explicit operator
action to resume automatic cycling.

## Broker-To-Hardware Test Procedure

1. Power off the Pi and verify wiring.
2. Run one-module-at-a-time direction tests.
3. Run the grouped sequence test.
4. Set `GPIO_ENABLED=true`, `MQTT_ENABLED=true`, broker settings and all four
   `TRAFFIC_LIGHT_*_LANE_ID` values in `raspberry-pi/.env`.
5. In `backend/.env`, set broker settings plus:

```env
HARDWARE_TEST_INTERSECTION_ID="backend-intersection-uuid"
HARDWARE_TEST_NORTH_LANE_ID="backend-north-lane-uuid"
HARDWARE_TEST_SOUTH_LANE_ID="backend-south-lane-uuid"
HARDWARE_TEST_EAST_LANE_ID="backend-east-lane-uuid"
HARDWARE_TEST_WEST_LANE_ID="backend-west-lane-uuid"
```

6. Start the MQTT broker:

```bash
sudo systemctl start mosquitto
```

7. Start the backend:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload
```

8. Start the edge service:

```bash
cd raspberry-pi
. .venv-gpio/bin/activate
python -m app.main
```

9. From the backend, send a typed command through the existing MQTT publisher:

```bash
cd backend
.venv/bin/python -m app.tools.hardware_signal_test --direction north --signal green --duration 5
```

The command prints the generated command ID, broker status, publish status,
matching `accepted` and `executed` acknowledgements, elapsed time and
`RESULT: PASS` or `RESULT: FAIL`.

Emergency all-red command:

```bash
cd backend
.venv/bin/python -m app.tools.hardware_signal_test --all-red --yes
```

Expected acknowledgements are `accepted` followed by `executed` for each
generated command ID. Rejected, failed, duplicate, malformed or timed-out
acknowledgements are test failures.

## Dashboard Synchronization Test

Do not perform this test until one-direction GPIO tests and the grouped
sequence pass.

1. Start Mosquitto:

```bash
sudo systemctl start mosquitto
```

2. Start the backend:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Start the Raspberry Pi edge service:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/raspberry-pi
. .venv-gpio/bin/activate
python -m app.main
```

4. Start the dashboard:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/web-dashboard
npm run dev -- --host 0.0.0.0 --port 5173
```

5. Open the Digital Twin for the configured intersection.
6. From the dashboard signal override, send north green.
7. Confirm the physical north module turns green and east/west remain red.
8. Confirm the Digital Twin changes only after the `executed` acknowledgement.
9. Wait for duration expiry.
10. Confirm physical lights return to all red.
11. Confirm the Digital Twin returns to all red after the restoration report.
12. Repeat for east green.
13. Run emergency all-red from the backend if needed:

```bash
cd /home/itms/Desktop/intelligent-traffic-management-system/backend
.venv/bin/python -m app.tools.hardware_signal_test --all-red --yes
```

## Rollback Procedure

If a light behaves incorrectly:

1. Stop the edge service with `Ctrl+C`; shutdown turns outputs off.
2. Set `GPIO_ENABLED=false` in `raspberry-pi/.env`.
3. Power off the Pi before touching wires.
4. Recheck shared ground, BCM pin mapping and lane-to-direction mapping.
5. Run direction tests again before re-enabling MQTT execution.
