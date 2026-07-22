from dataclasses import dataclass

import pytest

from app.intersection_test import ManualTestDurations, main as intersection_test_main
from app.traffic_light import (
    DisabledGPIOAdapter,
    FakeGPIOAdapter,
    IntersectionController,
    IntersectionPins,
    TrafficLightPins,
    create_intersection_controller,
)


@dataclass(frozen=True)
class GPIOTestSettings:
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


def test_four_configured_traffic_light_modules() -> None:
    controller = create_intersection_controller(GPIOTestSettings(), fake=True)

    assert controller.north.pins == TrafficLightPins(red=22, yellow=27, green=17)
    assert controller.south.pins == TrafficLightPins(red=5, yellow=6, green=13)
    assert controller.east.pins == TrafficLightPins(red=19, yellow=26, green=21)
    assert controller.west.pins == TrafficLightPins(red=16, yellow=20, green=12)


def test_unique_gpio_pins() -> None:
    pins = IntersectionPins.from_settings(GPIOTestSettings())

    assert len(pins.all_pins) == 12
    assert len(set(pins.all_pins)) == 12


def test_duplicate_gpio_pins_are_rejected() -> None:
    settings = GPIOTestSettings(traffic_light_west_green_pin=22)

    with pytest.raises(ValueError, match="duplicated"):
        create_intersection_controller(settings, fake=True)


def test_isolated_north_operation() -> None:
    controller, gpio = _controller()

    controller.north.show_green()

    _assert_one_light(gpio, controller.north.pins, "green")
    _assert_light_off(gpio, controller.south.pins)
    _assert_light_off(gpio, controller.east.pins)
    _assert_light_off(gpio, controller.west.pins)


def test_isolated_south_operation() -> None:
    controller, gpio = _controller()

    controller.south.show_yellow()

    _assert_one_light(gpio, controller.south.pins, "yellow")
    _assert_light_off(gpio, controller.north.pins)
    _assert_light_off(gpio, controller.east.pins)
    _assert_light_off(gpio, controller.west.pins)


def test_isolated_east_operation() -> None:
    controller, gpio = _controller()

    controller.east.show_red()

    _assert_one_light(gpio, controller.east.pins, "red")
    _assert_light_off(gpio, controller.north.pins)
    _assert_light_off(gpio, controller.south.pins)
    _assert_light_off(gpio, controller.west.pins)


def test_isolated_west_operation() -> None:
    controller, gpio = _controller()

    controller.west.show_green()

    _assert_one_light(gpio, controller.west.pins, "green")
    _assert_light_off(gpio, controller.north.pins)
    _assert_light_off(gpio, controller.south.pins)
    _assert_light_off(gpio, controller.east.pins)


def test_north_south_grouped_green_state() -> None:
    controller, gpio = _controller()

    controller.set_north_south_green()

    _assert_one_light(gpio, controller.north.pins, "green")
    _assert_one_light(gpio, controller.south.pins, "green")
    _assert_one_light(gpio, controller.east.pins, "red")
    _assert_one_light(gpio, controller.west.pins, "red")


def test_east_west_grouped_green_state() -> None:
    controller, gpio = _controller()

    controller.set_east_west_green()

    _assert_one_light(gpio, controller.east.pins, "green")
    _assert_one_light(gpio, controller.west.pins, "green")
    _assert_one_light(gpio, controller.north.pins, "red")
    _assert_one_light(gpio, controller.south.pins, "red")


def test_all_red_state() -> None:
    controller, gpio = _controller()

    controller.set_all_red()

    for light in controller.lights.values():
        _assert_one_light(gpio, light.pins, "red")


def test_conflicting_green_states_are_rejected() -> None:
    controller, gpio = _controller()

    controller.north.show_green()

    with pytest.raises(ValueError, match="Conflicting"):
        controller.east.show_green()

    _assert_one_light(gpio, controller.north.pins, "green")
    _assert_light_off(gpio, controller.east.pins)


def test_all_off_behavior() -> None:
    controller, gpio = _controller()

    controller.set_east_west_green()
    controller.all_off()

    assert all(value == gpio.LOW for value in gpio.pin_values.values())


def test_cleanup_turns_all_outputs_off() -> None:
    controller, gpio = _controller()

    controller.set_north_south_green()
    controller.cleanup()

    assert len(gpio.pin_values) == 12
    assert all(value == gpio.LOW for value in gpio.pin_values.values())
    assert gpio.cleaned_up is True


def test_fake_gpio_mode_sets_up_all_outputs() -> None:
    controller = create_intersection_controller(GPIOTestSettings(), fake=True)

    assert isinstance(controller.gpio, FakeGPIOAdapter)
    assert controller.gpio.mode == "BCM"
    assert len(controller.gpio.setups) == 12
    assert all(setup[2] == controller.gpio.LOW for setup in controller.gpio.setups)


def test_disabled_gpio_mode_does_not_import_rpi_gpio(monkeypatch) -> None:
    real_import = __import__

    def fail_on_rpi_gpio(name: str, *args: object, **kwargs: object) -> object:
        if name == "RPi.GPIO" or name.startswith("RPi"):
            raise AssertionError("RPi.GPIO must not be imported when GPIO is disabled")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fail_on_rpi_gpio)

    controller = create_intersection_controller(GPIOTestSettings(gpio_enabled=False))

    assert isinstance(controller.gpio, DisabledGPIOAdapter)


def test_intersection_manual_test_cleans_up_after_exception(monkeypatch) -> None:
    settings = GPIOTestSettings(gpio_enabled=False)
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)

    def fake_factory(created_settings: GPIOTestSettings) -> IntersectionController:
        assert created_settings == settings
        return controller

    def fail_sleep(_seconds: float) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.intersection_test._load_settings", lambda: settings)
    monkeypatch.setattr("app.intersection_test._load_durations", lambda _args: ManualTestDurations())
    monkeypatch.setattr("app.intersection_test.create_intersection_controller", fake_factory)
    monkeypatch.setattr("app.intersection_test.time.sleep", fail_sleep)

    with pytest.raises(RuntimeError):
        intersection_test_main(["--sequence"])

    assert all(value == gpio.LOW for value in gpio.pin_values.values())
    assert gpio.cleaned_up is True


def _controller() -> tuple[IntersectionController, FakeGPIOAdapter]:
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(GPIOTestSettings()), gpio)
    return controller, gpio


def _assert_one_light(gpio: FakeGPIOAdapter, pins: TrafficLightPins, active_colour: str) -> None:
    expected = {
        pins.red: gpio.HIGH if active_colour == "red" else gpio.LOW,
        pins.yellow: gpio.HIGH if active_colour == "yellow" else gpio.LOW,
        pins.green: gpio.HIGH if active_colour == "green" else gpio.LOW,
    }
    for pin, value in expected.items():
        assert gpio.pin_values[pin] == value


def _assert_light_off(gpio: FakeGPIOAdapter, pins: TrafficLightPins) -> None:
    for pin in pins.all_pins:
        assert gpio.pin_values[pin] == gpio.LOW
