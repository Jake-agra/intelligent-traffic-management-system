import uuid

from app.config import Settings


def test_configuration_loading(monkeypatch) -> None:
    device_id = uuid.uuid4()
    intersection_id = uuid.uuid4()
    monkeypatch.setenv("DEVICE_ID", str(device_id))
    monkeypatch.setenv("INTERSECTION_ID", str(intersection_id))
    monkeypatch.setenv("MQTT_ENABLED", "true")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("TRAFFIC_LIGHT_WEST_GREEN_PIN", "12")
    monkeypatch.setenv("TRAFFIC_LIGHT_NORTH_LANE_ID", str(uuid.uuid4()))
    monkeypatch.setenv("SIGNAL_COMMAND_MAX_DURATION_SECONDS", "45")

    settings = Settings(_env_file=None)

    assert settings.device_id == device_id
    assert settings.intersection_id == intersection_id
    assert settings.mqtt_enabled is True
    assert settings.heartbeat_interval_seconds == 5
    assert settings.traffic_light_north_red_pin == 22
    assert settings.traffic_light_west_green_pin == 12
    assert settings.traffic_light_north_lane_id is not None
    assert settings.signal_command_max_duration_seconds == 45
