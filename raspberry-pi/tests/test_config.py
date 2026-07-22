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

    settings = Settings(_env_file=None)

    assert settings.device_id == device_id
    assert settings.intersection_id == intersection_id
    assert settings.mqtt_enabled is True
    assert settings.heartbeat_interval_seconds == 5
    assert settings.traffic_light_north_red_pin == 22
    assert settings.traffic_light_west_green_pin == 12
