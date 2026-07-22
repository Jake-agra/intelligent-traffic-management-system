from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


DIRECTIONS = ("north", "south", "east", "west")
NORTH_SOUTH = frozenset(("north", "south"))
EAST_WEST = frozenset(("east", "west"))


@dataclass(frozen=True)
class TrafficLightPins:
    red: int
    yellow: int
    green: int

    @classmethod
    def from_legacy_settings(cls, settings: object) -> TrafficLightPins:
        return cls(
            red=int(getattr(settings, "traffic_light_red_pin")),
            yellow=int(getattr(settings, "traffic_light_yellow_pin")),
            green=int(getattr(settings, "traffic_light_green_pin")),
        )

    @property
    def all_pins(self) -> tuple[int, int, int]:
        return (self.red, self.yellow, self.green)


@dataclass(frozen=True)
class IntersectionPins:
    north: TrafficLightPins
    south: TrafficLightPins
    east: TrafficLightPins
    west: TrafficLightPins

    @classmethod
    def default(cls) -> IntersectionPins:
        return cls(
            north=TrafficLightPins(red=22, yellow=27, green=17),
            south=TrafficLightPins(red=5, yellow=6, green=13),
            east=TrafficLightPins(red=19, yellow=26, green=21),
            west=TrafficLightPins(red=16, yellow=20, green=12),
        )

    @classmethod
    def from_settings(cls, settings: IntersectionSettings) -> IntersectionPins:
        return cls(
            north=TrafficLightPins(
                red=settings.traffic_light_north_red_pin,
                yellow=settings.traffic_light_north_yellow_pin,
                green=settings.traffic_light_north_green_pin,
            ),
            south=TrafficLightPins(
                red=settings.traffic_light_south_red_pin,
                yellow=settings.traffic_light_south_yellow_pin,
                green=settings.traffic_light_south_green_pin,
            ),
            east=TrafficLightPins(
                red=settings.traffic_light_east_red_pin,
                yellow=settings.traffic_light_east_yellow_pin,
                green=settings.traffic_light_east_green_pin,
            ),
            west=TrafficLightPins(
                red=settings.traffic_light_west_red_pin,
                yellow=settings.traffic_light_west_yellow_pin,
                green=settings.traffic_light_west_green_pin,
            ),
        )

    @property
    def by_direction(self) -> dict[str, TrafficLightPins]:
        return {
            "north": self.north,
            "south": self.south,
            "east": self.east,
            "west": self.west,
        }

    @property
    def all_pins(self) -> tuple[int, ...]:
        return (
            *self.north.all_pins,
            *self.south.all_pins,
            *self.east.all_pins,
            *self.west.all_pins,
        )

    def validate_unique_pins(self) -> None:
        pins = self.all_pins
        duplicates = sorted({pin for pin in pins if pins.count(pin) > 1})
        if duplicates:
            duplicate_text = ", ".join(str(pin) for pin in duplicates)
            raise ValueError(f"GPIO pins must be unique; duplicated BCM pins: {duplicate_text}")


class IntersectionSettings(Protocol):
    gpio_enabled: bool
    traffic_light_north_red_pin: int
    traffic_light_north_yellow_pin: int
    traffic_light_north_green_pin: int
    traffic_light_south_red_pin: int
    traffic_light_south_yellow_pin: int
    traffic_light_south_green_pin: int
    traffic_light_east_red_pin: int
    traffic_light_east_yellow_pin: int
    traffic_light_east_green_pin: int
    traffic_light_west_red_pin: int
    traffic_light_west_yellow_pin: int
    traffic_light_west_green_pin: int


class GPIOAdapter(Protocol):
    OUT: object
    LOW: object
    HIGH: object

    def setmode_bcm(self) -> None:
        ...

    def setup_output(self, pin: int, initial: object) -> None:
        ...

    def output(self, pin: int, value: object) -> None:
        ...

    def cleanup(self) -> None:
        ...


class DisabledGPIOAdapter:
    OUT = "OUT"
    LOW = 0
    HIGH = 1

    def __init__(self) -> None:
        self.enabled = False

    def setmode_bcm(self) -> None:
        return None

    def setup_output(self, pin: int, initial: object) -> None:
        return None

    def output(self, pin: int, value: object) -> None:
        return None

    def cleanup(self) -> None:
        return None


class FakeGPIOAdapter:
    OUT = "OUT"
    LOW = 0
    HIGH = 1

    def __init__(self) -> None:
        self.mode: str | None = None
        self.setups: list[tuple[int, object, object]] = []
        self.outputs: list[tuple[int, object]] = []
        self.pin_values: dict[int, object] = {}
        self.cleaned_up = False

    def setmode_bcm(self) -> None:
        self.mode = "BCM"

    def setup_output(self, pin: int, initial: object) -> None:
        self.setups.append((pin, self.OUT, initial))
        self.pin_values[pin] = initial

    def output(self, pin: int, value: object) -> None:
        self.outputs.append((pin, value))
        self.pin_values[pin] = value

    def cleanup(self) -> None:
        self.cleaned_up = True


class RPiGPIOAdapter:
    def __init__(self) -> None:
        try:
            import RPi.GPIO as gpio
        except ImportError as exc:
            raise RuntimeError("Install RPi.GPIO or disable GPIO before running on this host.") from exc

        self._gpio = gpio
        self.OUT = gpio.OUT
        self.LOW = gpio.LOW
        self.HIGH = gpio.HIGH

    def setmode_bcm(self) -> None:
        self._gpio.setmode(self._gpio.BCM)

    def setup_output(self, pin: int, initial: object) -> None:
        self._gpio.setup(pin, self.OUT, initial=initial)

    def output(self, pin: int, value: object) -> None:
        self._gpio.output(pin, value)

    def cleanup(self) -> None:
        self._gpio.cleanup()


class TrafficLight:
    def __init__(
        self,
        direction: str,
        pins: TrafficLightPins,
        gpio: GPIOAdapter,
        before_green: Callable[[str], None] | None = None,
    ) -> None:
        self.direction = direction
        self.pins = pins
        self.gpio = gpio
        self._before_green = before_green
        self.active_colour: str | None = None
        self.gpio.setmode_bcm()
        for pin in self.pins.all_pins:
            self.gpio.setup_output(pin, self.gpio.LOW)

    def show_red(self) -> None:
        self._show_only("red", self.pins.red)

    def show_yellow(self) -> None:
        self._show_only("yellow", self.pins.yellow)

    def show_green(self) -> None:
        if self._before_green is not None:
            self._before_green(self.direction)
        self._show_only("green", self.pins.green)

    def all_off(self) -> None:
        for pin in self.pins.all_pins:
            self.gpio.output(pin, self.gpio.LOW)
        self.active_colour = None

    def cleanup(self) -> None:
        self.all_off()
        self.gpio.cleanup()

    def _show_only(self, colour: str, active_pin: int) -> None:
        for pin in self.pins.all_pins:
            if pin != active_pin:
                self.gpio.output(pin, self.gpio.LOW)
        self.gpio.output(active_pin, self.gpio.HIGH)
        self.active_colour = colour


class IntersectionController:
    def __init__(self, pins: IntersectionPins, gpio: GPIOAdapter) -> None:
        pins.validate_unique_pins()
        self.pins = pins
        self.gpio = gpio
        self.north = TrafficLight("north", pins.north, gpio, self._before_green)
        self.south = TrafficLight("south", pins.south, gpio, self._before_green)
        self.east = TrafficLight("east", pins.east, gpio, self._before_green)
        self.west = TrafficLight("west", pins.west, gpio, self._before_green)

    @property
    def lights(self) -> dict[str, TrafficLight]:
        return {
            "north": self.north,
            "south": self.south,
            "east": self.east,
            "west": self.west,
        }

    def light_for(self, direction: str) -> TrafficLight:
        normalized = direction.lower()
        try:
            return self.lights[normalized]
        except KeyError as exc:
            raise ValueError(f"Unknown traffic-light direction: {direction}") from exc

    def set_north_south_green(self) -> None:
        self.set_green_directions(("north", "south"))

    def set_east_west_green(self) -> None:
        self.set_green_directions(("east", "west"))

    def set_green_directions(self, directions: Iterable[str]) -> None:
        requested = {direction.lower() for direction in directions}
        unknown = requested.difference(DIRECTIONS)
        if unknown:
            unknown_text = ", ".join(sorted(unknown))
            raise ValueError(f"Unknown traffic-light direction: {unknown_text}")
        if requested.intersection(NORTH_SOUTH) and requested.intersection(EAST_WEST):
            raise ValueError("Conflicting green phases are not allowed.")

        for direction, light in self.lights.items():
            if direction not in requested:
                light.show_red()
        for direction, light in self.lights.items():
            if direction in requested:
                light.show_green()

    def set_all_red(self) -> None:
        for light in self.lights.values():
            light.show_red()

    def all_off(self) -> None:
        for light in self.lights.values():
            light.all_off()

    def cleanup(self) -> None:
        self.all_off()
        self.gpio.cleanup()

    def _before_green(self, direction: str) -> None:
        current_green = {
            light_direction
            for light_direction, light in self.lights.items()
            if light_direction != direction and light.active_colour == "green"
        }
        if direction in NORTH_SOUTH and current_green.intersection(EAST_WEST):
            raise ValueError("Conflicting green phases are not allowed.")
        if direction in EAST_WEST and current_green.intersection(NORTH_SOUTH):
            raise ValueError("Conflicting green phases are not allowed.")


def create_gpio_adapter(settings: object, *, fake: bool = False) -> GPIOAdapter:
    if fake:
        return FakeGPIOAdapter()
    if bool(getattr(settings, "gpio_enabled", False)):
        return RPiGPIOAdapter()
    return DisabledGPIOAdapter()


def create_intersection_controller(
    settings: IntersectionSettings,
    *,
    fake: bool = False,
) -> IntersectionController:
    return IntersectionController(
        IntersectionPins.from_settings(settings),
        create_gpio_adapter(settings, fake=fake),
    )


def create_traffic_light_driver(settings: object, *, fake: bool = False) -> TrafficLight:
    return TrafficLight(
        "north",
        TrafficLightPins.from_legacy_settings(settings),
        create_gpio_adapter(settings, fake=fake),
    )


TrafficLightDriver = TrafficLight
