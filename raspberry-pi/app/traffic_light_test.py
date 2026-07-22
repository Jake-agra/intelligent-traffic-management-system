from __future__ import annotations

from dataclasses import dataclass
import os
import time
from collections.abc import Callable
from pathlib import Path

from app.traffic_light import create_traffic_light_driver


@dataclass(frozen=True)
class ManualTrafficLightSettings:
    gpio_enabled: bool = False
    traffic_light_green_pin: int = 17
    traffic_light_yellow_pin: int = 27
    traffic_light_red_pin: int = 22
    config_path: Path | None = None


def main() -> None:
    settings = _load_settings()
    driver = create_traffic_light_driver(settings)

    print("Traffic light GPIO manual test")
    print(f"Config file: {settings.config_path or 'not found; using environment/defaults'}")
    print(f"GPIO enabled: {settings.gpio_enabled}")
    print(f"BCM pin mapping: green={driver.pins.green}, yellow={driver.pins.yellow}, red={driver.pins.red}")

    try:
        _show(driver.show_red, driver.all_off, "red", 3)
        _show(driver.show_yellow, driver.all_off, "yellow", 3)
        _show(driver.show_green, driver.all_off, "green", 3)

        print("Running sequence: red 3s, yellow 2s, green 3s, yellow 2s, red 3s")
        _show(driver.show_red, driver.all_off, "red", 3)
        _show(driver.show_yellow, driver.all_off, "yellow", 2)
        _show(driver.show_green, driver.all_off, "green", 3)
        _show(driver.show_yellow, driver.all_off, "yellow", 2)
        _show(driver.show_red, driver.all_off, "red", 3)

        print("Turning all lights off")
        driver.all_off()
    except KeyboardInterrupt:
        print("Interrupted; turning all lights off")
    finally:
        driver.cleanup()
        print("GPIO cleanup complete")


def _show(show: Callable[[], None], all_off: Callable[[], None], colour: str, seconds: int) -> None:
    unit = "second" if seconds == 1 else "seconds"
    print(f"Turning {colour} on for {seconds} {unit}")
    show()
    time.sleep(seconds)
    print("Turning all lights off")
    all_off()


def _load_settings() -> ManualTrafficLightSettings:
    env_path = _find_env_file()
    values = _load_env_file(env_path) if env_path else {}
    values.update(os.environ)
    return ManualTrafficLightSettings(
        gpio_enabled=_bool_value(values.get("GPIO_ENABLED"), default=False),
        traffic_light_green_pin=_int_value(values.get("TRAFFIC_LIGHT_GREEN_PIN"), default=17),
        traffic_light_yellow_pin=_int_value(values.get("TRAFFIC_LIGHT_YELLOW_PIN"), default=27),
        traffic_light_red_pin=_int_value(values.get("TRAFFIC_LIGHT_RED_PIN"), default=22),
        config_path=env_path,
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


if __name__ == "__main__":
    main()
