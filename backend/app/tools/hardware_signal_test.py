from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import time
import uuid

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.models.enums import SignalColor
from app.mqtt.client import MQTTClientProtocol, PahoMQTTClient
from app.mqtt.topics import SIGNAL_ACK_TOPIC, signal_command_topic
from app.schemas.mqtt import SignalCommandAckPayload, SignalCommandPayload
from app.services.mqtt import MQTTService


DIRECTIONS = ("north", "south", "east", "west")
PASS_STATUSES = {"accepted", "executed"}
FAIL_STATUSES = {"rejected", "failed", "duplicate"}
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class HardwareSignalTestRequest:
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    direction: str
    signal: SignalColor
    duration_seconds: int
    timeout_seconds: float
    yes: bool


@dataclass(frozen=True)
class AcknowledgementRecord:
    status: str
    acknowledged_at: datetime
    message: str | None


@dataclass
class HardwareSignalTestResult:
    command_id: uuid.UUID
    passed: bool
    acknowledgements: list[AcknowledgementRecord]
    error: str | None
    elapsed_seconds: float
    broker_connected: bool
    command_published: bool


class CommandAckObserver:
    def __init__(
        self,
        *,
        service: MQTTService,
        command_id: uuid.UUID,
    ) -> None:
        self.service = service
        self.command_id = command_id
        self.records: list[AcknowledgementRecord] = []
        self.failure: str | None = None
        self._event = asyncio.Event()

    async def handle_message(self, topic: str, payload: bytes) -> None:
        await self.service.handle_message(topic, payload)
        try:
            ack = SignalCommandAckPayload.model_validate_json(payload)
        except (ValidationError, ValueError) as exc:
            self.failure = f"Malformed acknowledgement: {exc}"
            self._event.set()
            return

        if ack.command_id != self.command_id:
            return

        record = AcknowledgementRecord(
            status=ack.status,
            acknowledged_at=ack.acknowledged_at,
            message=ack.message,
        )
        self.records.append(record)
        if ack.status in FAIL_STATUSES:
            self.failure = f"Command acknowledgement reported {ack.status}: {ack.message}"
        self._event.set()

    async def wait_for_update(self, timeout_seconds: float) -> None:
        await asyncio.wait_for(self._event.wait(), timeout=timeout_seconds)
        self._event.clear()

    def has_required_success(self) -> bool:
        statuses = {record.status for record in self.records}
        return PASS_STATUSES.issubset(statuses)


class HardwareSignalTestRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        client: MQTTClientProtocol | None = None,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.client = client or PahoMQTTClient(_tool_client_settings(settings))
        self.sleep = sleep
        self.service = MQTTService(client=self.client, session_factory=_unused_session_factory)

    async def run(self, request: HardwareSignalTestRequest) -> HardwareSignalTestResult:
        started_at = time.monotonic()
        command = SignalCommandPayload(
            command_id=uuid.uuid4(),
            intersection_id=request.intersection_id,
            lane_id=request.lane_id,
            signal=request.signal,
            duration_seconds=request.duration_seconds,
            reason=f"hardware_signal_test_{request.direction}",
            issued_at=datetime.now(UTC),
        )
        observer = CommandAckObserver(service=self.service, command_id=command.command_id)
        self.client.set_message_handler(observer.handle_message)

        try:
            await self.client.connect()
        except Exception as exc:
            return HardwareSignalTestResult(
                command_id=command.command_id,
                passed=False,
                acknowledgements=[],
                error=f"Broker connection failed: {exc}",
                elapsed_seconds=time.monotonic() - started_at,
                broker_connected=False,
                command_published=False,
            )

        command_published = False
        try:
            await self.client.subscribe(_ack_topic(command.intersection_id))
            await self.service.publish_signal_command(command)
            command_published = True
            while not observer.has_required_success():
                if observer.failure is not None:
                    return _failed_result(command.command_id, observer, observer.failure, started_at)
                try:
                    await observer.wait_for_update(request.timeout_seconds)
                except asyncio.TimeoutError:
                    return _failed_result(
                        command.command_id,
                        observer,
                        "Timed out waiting for accepted and executed acknowledgements.",
                        started_at,
                    )

            await self.sleep(request.duration_seconds)
            return HardwareSignalTestResult(
                command_id=command.command_id,
                passed=True,
                acknowledgements=observer.records,
                error=None,
                elapsed_seconds=time.monotonic() - started_at,
                broker_connected=True,
                command_published=True,
            )
        except Exception as exc:
            return HardwareSignalTestResult(
                command_id=command.command_id,
                passed=False,
                acknowledgements=observer.records,
                error=f"Command publish or acknowledgement handling failed: {exc}",
                elapsed_seconds=time.monotonic() - started_at,
                broker_connected=True,
                command_published=command_published,
            )
        finally:
            await self.client.disconnect()


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    settings = get_settings()
    requests = _requests_from_args(args, settings)

    _print_emergency_procedure()
    for request in requests:
        _print_request(settings, request)
        if not request.yes and not _confirm():
            print("RESULT: CANCELLED")
            return
        result = asyncio.run(HardwareSignalTestRunner(settings=settings).run(request))
        _print_result(result)
        if not result.passed:
            raise SystemExit(1)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a controlled MQTT broker-to-hardware signal test."
    )
    parser.add_argument("--direction", choices=DIRECTIONS)
    parser.add_argument(
        "--signal",
        choices=[item.value for item in SignalColor],
        default=SignalColor.GREEN.value,
    )
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--all-red", action="store_true")
    return parser.parse_args(argv)


def _requests_from_args(
    args: argparse.Namespace,
    settings: Settings,
) -> list[HardwareSignalTestRequest]:
    _validate_duration(args.duration)
    _validate_timeout(args.timeout)
    intersection_id = _require_uuid(
        settings.hardware_test_intersection_id,
        "HARDWARE_TEST_INTERSECTION_ID",
    )

    if args.all_red:
        return [
            _request_for_direction(
                settings=settings,
                direction=direction,
                signal=SignalColor.RED,
                duration_seconds=args.duration,
                timeout_seconds=args.timeout,
                yes=args.yes,
                intersection_id=intersection_id,
            )
            for direction in DIRECTIONS
        ]

    if args.direction is None:
        raise SystemExit("--direction is required unless --all-red is used.")
    return [
        _request_for_direction(
            settings=settings,
            direction=args.direction,
            signal=SignalColor(args.signal),
            duration_seconds=args.duration,
            timeout_seconds=args.timeout,
            yes=args.yes,
            intersection_id=intersection_id,
        )
    ]


def _request_for_direction(
    *,
    settings: Settings,
    direction: str,
    signal: SignalColor,
    duration_seconds: int,
    timeout_seconds: float,
    yes: bool,
    intersection_id: uuid.UUID,
) -> HardwareSignalTestRequest:
    lane_id = _require_uuid(
        _lane_mapping(settings)[direction],
        f"HARDWARE_TEST_{direction.upper()}_LANE_ID",
    )
    return HardwareSignalTestRequest(
        intersection_id=intersection_id,
        lane_id=lane_id,
        direction=direction,
        signal=signal,
        duration_seconds=duration_seconds,
        timeout_seconds=timeout_seconds,
        yes=yes,
    )


def _lane_mapping(settings: Settings) -> dict[str, uuid.UUID | None]:
    return {
        "north": settings.hardware_test_north_lane_id,
        "south": settings.hardware_test_south_lane_id,
        "east": settings.hardware_test_east_lane_id,
        "west": settings.hardware_test_west_lane_id,
    }


def _tool_client_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"mqtt_client_id": f"{settings.mqtt_client_id}-hardware-test-{uuid.uuid4()}"}
    )


def _require_uuid(value: uuid.UUID | None, setting_name: str) -> uuid.UUID:
    if value is None:
        raise SystemExit(f"{setting_name} must be configured before running the hardware test.")
    return value


def _validate_duration(duration: int) -> None:
    if duration < 1:
        raise SystemExit("--duration must be at least 1 second.")


def _validate_timeout(timeout: float) -> None:
    if timeout <= 0:
        raise SystemExit("--timeout must be greater than 0 seconds.")


def _print_emergency_procedure() -> None:
    print("Emergency all-red procedure:")
    print("1. Run: python -m app.tools.hardware_signal_test --all-red --yes")
    print("2. Stop the Raspberry Pi edge service with Ctrl+C if lights remain unsafe.")
    print("3. Power off the Pi before changing wiring.")
    print()


def _print_request(settings: Settings, request: HardwareSignalTestRequest) -> None:
    print("Hardware Signal Test")
    print()
    print(f"Direction: {request.direction}")
    print(f"Signal: {request.signal.value}")
    print(f"Duration: {request.duration_seconds} seconds")
    print(f"Broker: {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
    print(f"Publish topic: {signal_command_topic(request.intersection_id)}")
    print()


def _confirm() -> bool:
    answer = input("Send this command to physical hardware? Type 'yes' to continue: ")
    return answer.strip().lower() == "yes"


def _print_result(result: HardwareSignalTestResult) -> None:
    print(f"Command ID: {result.command_id}")
    print(f"Broker: {'Connected' if result.broker_connected else 'Unavailable'}")
    print(f"Command: {'Published' if result.command_published else 'Not published'}")
    if result.error:
        print(f"Error: {result.error}")
    for record in result.acknowledgements:
        print(
            f"Acknowledgement: {record.status.title()} "
            f"at {record.acknowledged_at.isoformat()}"
        )
        if record.message:
            print(f"Message: {record.message}")
    print(f"Total elapsed: {result.elapsed_seconds:.2f} seconds")
    print()
    print("RESULT: PASS" if result.passed else "RESULT: FAIL")


def _failed_result(
    command_id: uuid.UUID,
    observer: CommandAckObserver,
    error: str,
    started_at: float,
) -> HardwareSignalTestResult:
    return HardwareSignalTestResult(
        command_id=command_id,
        passed=False,
        acknowledgements=observer.records,
        error=error,
        elapsed_seconds=time.monotonic() - started_at,
        broker_connected=True,
        command_published=True,
    )


def _ack_topic(intersection_id: uuid.UUID) -> str:
    return SIGNAL_ACK_TOPIC.format(intersection_id=intersection_id)


@contextmanager
def _unused_session_factory() -> object:
    yield None


if __name__ == "__main__":
    main()
