from __future__ import annotations

from collections.abc import Awaitable
import asyncio
from datetime import UTC, datetime
import json
import uuid

import pytest

from app.core.config import Settings
from app.models.enums import SignalColor
from app.mqtt.client import MessageHandler
from app.mqtt.topics import SIGNAL_ACK_TOPIC, signal_command_topic
from app.schemas.mqtt import SignalCommandAckPayload
from app.tools.hardware_signal_test import (
    HardwareSignalTestRequest,
    HardwareSignalTestRunner,
    _parse_args,
    _requests_from_args,
)


class FakeMQTTClient:
    def __init__(
        self,
        *,
        acknowledgements: list[str] | None = None,
        connect_error: Exception | None = None,
        include_wrong_command_ack: bool = False,
    ) -> None:
        self.acknowledgements = (
            ["accepted", "executed"] if acknowledgements is None else acknowledgements
        )
        self.connect_error = connect_error
        self.include_wrong_command_ack = include_wrong_command_ack
        self.handler: MessageHandler | None = None
        self.subscriptions: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.connected = False

    async def connect(self) -> None:
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))
        if self.handler is None:
            return
        command = json.loads(payload)
        ack_topic = SIGNAL_ACK_TOPIC.format(intersection_id=command["intersection_id"])
        if self.include_wrong_command_ack:
            await self._emit_ack(ack_topic, command, status="accepted", command_id=uuid.uuid4())
        for status in self.acknowledgements:
            await self._emit_ack(ack_topic, command, status=status)

    def set_message_handler(self, handler: MessageHandler) -> None:
        self.handler = handler

    async def _emit_ack(
        self,
        topic: str,
        command: dict[str, object],
        *,
        status: str,
        command_id: uuid.UUID | None = None,
    ) -> None:
        assert self.handler is not None
        ack = SignalCommandAckPayload(
            command_id=command_id or uuid.UUID(str(command["command_id"])),
            intersection_id=uuid.UUID(str(command["intersection_id"])),
            lane_id=uuid.UUID(str(command["lane_id"])),
            status=status,
            message=f"{status} acknowledgement",
            acknowledged_at=datetime.now(UTC),
        )
        await self.handler(topic, ack.model_dump_json().encode("utf-8"))


@pytest.fixture
def hardware_settings() -> Settings:
    return Settings(
        hardware_test_intersection_id=uuid.uuid4(),
        hardware_test_north_lane_id=uuid.uuid4(),
        hardware_test_south_lane_id=uuid.uuid4(),
        hardware_test_east_lane_id=uuid.uuid4(),
        hardware_test_west_lane_id=uuid.uuid4(),
        mqtt_broker_host="mqtt.local",
    )


async def _no_sleep(_seconds: float) -> None:
    return None


def test_valid_publish(hardware_settings: Settings) -> None:
    client = FakeMQTTClient()
    request = _north_request(hardware_settings)

    result = _run(
        HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep).run(request)
    )

    assert result.passed
    assert client.published[0][0] == signal_command_topic(request.intersection_id)
    payload = json.loads(client.published[0][1])
    assert payload["lane_id"] == str(hardware_settings.hardware_test_north_lane_id)
    assert payload["signal"] == SignalColor.GREEN.value


def test_acknowledgement_correlation(hardware_settings: Settings) -> None:
    client = FakeMQTTClient(include_wrong_command_ack=True)

    result = _run(
        HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep).run(
            _north_request(hardware_settings)
        )
    )

    assert result.passed
    assert [record.status for record in result.acknowledgements] == ["accepted", "executed"]


def test_timeout(hardware_settings: Settings) -> None:
    client = FakeMQTTClient(acknowledgements=[])
    request = _north_request(hardware_settings, timeout_seconds=0.01)

    result = _run(
        HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep).run(request)
    )

    assert not result.passed
    assert "Timed out" in str(result.error)


@pytest.mark.parametrize("status", ["rejected", "failed"])
def test_rejection(status: str, hardware_settings: Settings) -> None:
    client = FakeMQTTClient(acknowledgements=[status])

    result = _run(
        HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep).run(
            _north_request(hardware_settings)
        )
    )

    assert not result.passed
    assert status in str(result.error)


def test_duplicate_acknowledgement(hardware_settings: Settings) -> None:
    client = FakeMQTTClient(acknowledgements=["duplicate"])

    result = _run(
        HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep).run(
            _north_request(hardware_settings)
        )
    )

    assert not result.passed
    assert "duplicate" in str(result.error)


def test_invalid_direction() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--direction", "up"])


def test_invalid_duration(hardware_settings: Settings) -> None:
    args = _parse_args(["--direction", "north", "--duration", "0"])

    with pytest.raises(SystemExit, match="duration"):
        _requests_from_args(args, hardware_settings)


def test_broker_unavailable(hardware_settings: Settings) -> None:
    client = FakeMQTTClient(connect_error=RuntimeError("broker down"))

    result = _run(
        HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep).run(
            _north_request(hardware_settings)
        )
    )

    assert not result.passed
    assert not result.broker_connected
    assert result.command_published is False


def test_emergency_all_red(hardware_settings: Settings) -> None:
    args = _parse_args(["--all-red", "--yes"])

    requests = _requests_from_args(args, hardware_settings)

    assert [request.direction for request in requests] == ["north", "south", "east", "west"]
    assert {request.signal for request in requests} == {SignalColor.RED}


def test_unique_command_ids(hardware_settings: Settings) -> None:
    client = FakeMQTTClient()
    runner = HardwareSignalTestRunner(settings=hardware_settings, client=client, sleep=_no_sleep)

    first = _run(runner.run(_north_request(hardware_settings)))
    second = _run(runner.run(_north_request(hardware_settings)))

    assert first.command_id != second.command_id
    published_ids = [json.loads(payload)["command_id"] for _topic, payload in client.published]
    assert len(set(published_ids)) == 2


def _north_request(
    settings: Settings,
    *,
    timeout_seconds: float = 1,
) -> HardwareSignalTestRequest:
    assert settings.hardware_test_intersection_id is not None
    assert settings.hardware_test_north_lane_id is not None
    return HardwareSignalTestRequest(
        intersection_id=settings.hardware_test_intersection_id,
        lane_id=settings.hardware_test_north_lane_id,
        direction="north",
        signal=SignalColor.GREEN,
        duration_seconds=1,
        timeout_seconds=timeout_seconds,
        yes=True,
    )


def _run(awaitable: Awaitable[object]) -> object:
    return asyncio.run(awaitable)
