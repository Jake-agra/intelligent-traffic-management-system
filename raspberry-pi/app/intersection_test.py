from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import time

from app.traffic_light import (
    DIRECTIONS,
    IntersectionController,
    IntersectionPins,
    TrafficLight,
    create_intersection_controller,
)


@dataclass(frozen=True)
class ManualIntersectionSettings:
    gpio_enabled: bool = False
    traffic_light_north_red_pin: int = 22
    traffic_light_north_yellow_pin: int = 27
    traffic_light_north_green_pin: int = 17
    traffic_light_south_red_pin: int = 5
    traffic_light_south_yellow_pin: int = 6
    traffic_light_south_green_pin: int = 13
    traffic_light_east_red_pin: int = 19
    traffic_light_east_yellow_pin: int = 26
    traffic_light_east_green_pin: int = 21
    traffic_light_west_red_pin: int = 16
    traffic_light_west_yellow_pin: int = 20
    traffic_light_west_green_pin: int = 12
    config_path: Path | None = None


@dataclass(frozen=True)
class ManualTestDurations:
    red: float = 2
    yellow: float = 1
    green: float = 2
    all_red: float = 1


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    settings = _load_settings()
    durations = _load_durations(args)
    pins = IntersectionPins.from_settings(settings)

    print("Four-way intersection GPIO manual test")
    config_path = getattr(settings, "config_path", None)
    print(f"Config file: {config_path or 'not found; using environment/defaults'}")
    print(f"GPIO enabled: {settings.gpio_enabled}")
    _print_mapping(pins)

    controller = create_intersection_controller(settings)
    try:
        if args.direction:
            _run_direction_test(controller, args.direction, durations)
        else:
            _run_sequence_test(controller, durations)
    except KeyboardInterrupt:
        print("Interrupted; turning all outputs off")
    finally:
        controller.cleanup()
        print("GPIO cleanup complete")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual four-way traffic-light GPIO test.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--direction", choices=DIRECTIONS)
    mode.add_argument("--sequence", action="store_true")
    parser.add_argument("--red-seconds", type=float)
    parser.add_argument("--yellow-seconds", type=float)
    parser.add_argument("--green-seconds", type=float)
    parser.add_argument("--all-red-seconds", type=float)
    return parser.parse_args(argv)


def _run_direction_test(
    controller: IntersectionController,
    direction: str,
    durations: ManualTestDurations,
) -> None:
    light = controller.light_for(direction)
    print(f"Selected direction: {direction}")
    _print_light_mapping(direction, light)
    _show(light.show_red, f"{direction} red", durations.red)
    _show(light.show_yellow, f"{direction} yellow", durations.yellow)
    _show(light.show_green, f"{direction} green", durations.green)
    _show(light.show_red, f"{direction} red", durations.red)
    print("Turning all outputs off")
    controller.all_off()


def _run_sequence_test(controller: IntersectionController, durations: ManualTestDurations) -> None:
    print("Running grouped sequence")
    _show(controller.set_all_red, "all red", durations.all_red)
    _show(controller.set_north_south_green, "north/south green and east/west red", durations.green)
    _show(lambda: _set_yellow_pair(controller.north, controller.south), "north/south yellow", durations.yellow)
    _show(controller.set_all_red, "all red", durations.all_red)
    _show(controller.set_east_west_green, "east/west green and north/south red", durations.green)
    _show(lambda: _set_yellow_pair(controller.east, controller.west), "east/west yellow", durations.yellow)
    _show(controller.set_all_red, "all red", durations.all_red)
    print("Turning all outputs off")
    controller.all_off()


def _set_yellow_pair(first: TrafficLight, second: TrafficLight) -> None:
    first.show_yellow()
    second.show_yellow()


def _show(action: Callable[[], None], label: str, seconds: float) -> None:
    unit = "second" if seconds == 1 else "seconds"
    print(f"Showing {label} for {seconds:g} {unit}")
    action()
    time.sleep(seconds)


def _print_mapping(pins: IntersectionPins) -> None:
    for direction, light_pins in pins.by_direction.items():
        print(
            f"{direction}: red={light_pins.red}, "
            f"yellow={light_pins.yellow}, green={light_pins.green}"
        )


def _print_light_mapping(direction: str, light: TrafficLight) -> None:
    print(
        f"{direction} BCM pin mapping: red={light.pins.red}, "
        f"yellow={light.pins.yellow}, green={light.pins.green}"
    )


def _load_settings() -> ManualIntersectionSettings:
    env_path = _find_env_file()
    values = _load_env_file(env_path) if env_path else {}
    values.update(os.environ)
    return ManualIntersectionSettings(
        gpio_enabled=_bool_value(values.get("GPIO_ENABLED"), default=False),
        traffic_light_north_red_pin=_int_value(values.get("TRAFFIC_LIGHT_NORTH_RED_PIN"), default=22),
        traffic_light_north_yellow_pin=_int_value(values.get("TRAFFIC_LIGHT_NORTH_YELLOW_PIN"), default=27),
        traffic_light_north_green_pin=_int_value(values.get("TRAFFIC_LIGHT_NORTH_GREEN_PIN"), default=17),
        traffic_light_south_red_pin=_int_value(values.get("TRAFFIC_LIGHT_SOUTH_RED_PIN"), default=5),
        traffic_light_south_yellow_pin=_int_value(values.get("TRAFFIC_LIGHT_SOUTH_YELLOW_PIN"), default=6),
        traffic_light_south_green_pin=_int_value(values.get("TRAFFIC_LIGHT_SOUTH_GREEN_PIN"), default=13),
        traffic_light_east_red_pin=_int_value(values.get("TRAFFIC_LIGHT_EAST_RED_PIN"), default=19),
        traffic_light_east_yellow_pin=_int_value(values.get("TRAFFIC_LIGHT_EAST_YELLOW_PIN"), default=26),
        traffic_light_east_green_pin=_int_value(values.get("TRAFFIC_LIGHT_EAST_GREEN_PIN"), default=21),
        traffic_light_west_red_pin=_int_value(values.get("TRAFFIC_LIGHT_WEST_RED_PIN"), default=16),
        traffic_light_west_yellow_pin=_int_value(values.get("TRAFFIC_LIGHT_WEST_YELLOW_PIN"), default=20),
        traffic_light_west_green_pin=_int_value(values.get("TRAFFIC_LIGHT_WEST_GREEN_PIN"), default=12),
        config_path=env_path,
    )


def _load_durations(args: argparse.Namespace) -> ManualTestDurations:
    env_path = _find_env_file()
    values = _load_env_file(env_path) if env_path else {}
    values.update(os.environ)
    return ManualTestDurations(
        red=args.red_seconds
        if args.red_seconds is not None
        else _float_value(values.get("INTERSECTION_TEST_RED_SECONDS"), default=2),
        yellow=args.yellow_seconds
        if args.yellow_seconds is not None
        else _float_value(values.get("INTERSECTION_TEST_YELLOW_SECONDS"), default=1),
        green=args.green_seconds
        if args.green_seconds is not None
        else _float_value(values.get("INTERSECTION_TEST_GREEN_SECONDS"), default=2),
        all_red=args.all_red_seconds
        if args.all_red_seconds is not None
        else _float_value(values.get("INTERSECTION_TEST_ALL_RED_SECONDS"), default=1),
    )


def _find_env_file() -> Path | None:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _bool_value(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_value(value: str | None, *, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _float_value(value: str | None, *, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    return float(value)


if __name__ == "__main__":
    main()
