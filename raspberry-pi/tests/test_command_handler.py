import asyncio
from datetime import UTC, datetime, timedelta
import json
import uuid

from app.command_handler import CommandHandler, signal_ack_topic
from app.config import Settings
from app.mqtt_client import FakeMQTTClient
from app.schemas import CommandAckStatus, SignalColor, SignalCommandPayload


def test_valid_command_acceptance() -> None:
    settings = _settings()
    handler = CommandHandler(settings, FakeMQTTClient())
    command = _command(settings)

    ack = handler.handle_command(command)

    assert ack.status == CommandAckStatus.ACCEPTED
    assert ack.device_id == settings.device_id
    assert ack.command_id == command.command_id


def test_invalid_command_rejection() -> None:
    settings = _settings()
    handler = CommandHandler(settings, FakeMQTTClient())
    command = _command(settings, intersection_id=uuid.uuid4())

    ack = handler.handle_command(command)

    assert ack.status == CommandAckStatus.REJECTED
    assert "intersection" in ack.message


def test_stale_command_rejection() -> None:
    settings = _settings(command_max_age_seconds=10)
    handler = CommandHandler(settings, FakeMQTTClient())
    command = _command(settings, issued_at=datetime.now(UTC) - timedelta(seconds=20))

    ack = handler.handle_command(command)

    assert ack.status == CommandAckStatus.REJECTED
    assert "stale" in ack.message


def test_acknowledgement_publishing() -> None:
    settings = _settings()
    mqtt_client = FakeMQTTClient()
    handler = CommandHandler(settings, mqtt_client)
    command = _command(settings)

    ack = asyncio.run(handler.handle_message("ignored", command.model_dump_json().encode()))

    assert ack.status == CommandAckStatus.ACCEPTED
    assert mqtt_client.published[0][0] == signal_ack_topic(settings.intersection_id)
    body = json.loads(mqtt_client.published[0][1])
    assert body["device_id"] == str(settings.device_id)
    assert body["status"] == CommandAckStatus.ACCEPTED.value


def test_malformed_command_publishes_rejection_ack() -> None:
    settings = _settings()
    mqtt_client = FakeMQTTClient()
    handler = CommandHandler(settings, mqtt_client)

    ack = asyncio.run(handler.handle_message("ignored", b"{bad-json"))

    assert ack.status == CommandAckStatus.REJECTED
    assert mqtt_client.published


def _settings(**overrides: object) -> Settings:
    values = {
        "device_id": uuid.uuid4(),
        "intersection_id": uuid.uuid4(),
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _command(
    settings: Settings,
    *,
    intersection_id: uuid.UUID | None = None,
    issued_at: datetime | None = None,
) -> SignalCommandPayload:
    return SignalCommandPayload(
        command_id=uuid.uuid4(),
        intersection_id=intersection_id or settings.intersection_id,
        lane_id=uuid.uuid4(),
        signal=SignalColor.GREEN,
        duration_seconds=20,
        reason="adaptive_density_control",
        issued_at=issued_at or datetime.now(UTC),
    )
