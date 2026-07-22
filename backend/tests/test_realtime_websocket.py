import asyncio
import uuid

import pytest

from app.api.routes.v1.websocket import _parse_event_filter
from app.realtime import realtime_event_publisher, websocket_manager
from app.schemas.realtime import RealtimeEventEnvelope, RealtimeEventName


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        self.sent.append(message)


@pytest.fixture(autouse=True)
def reset_websocket_manager() -> None:
    websocket_manager.reset()


def test_websocket_sends_connection_acknowledgement() -> None:
    websocket = FakeWebSocket()

    _connect(websocket)
    message = websocket.sent[0]

    assert message["type"] == "connection.acknowledged"
    assert message["version"] == 1
    assert message["subscription"] == {"intersection_id": None, "events": None}
    assert RealtimeEventName.TRAFFIC_UPDATED.value in message["supported_events"]


def test_event_broadcast_reaches_two_clients() -> None:
    event = RealtimeEventEnvelope(
        event=RealtimeEventName.TRAFFIC_UPDATED,
        data={"vehicle_count": 8},
    )
    first = FakeWebSocket()
    second = FakeWebSocket()

    _connect(first)
    _connect(second)
    delivered = _run(realtime_event_publisher.publish(event))

    assert delivered == 2
    assert first.sent[1]["event"] == RealtimeEventName.TRAFFIC_UPDATED.value
    assert second.sent[1]["event"] == RealtimeEventName.TRAFFIC_UPDATED.value


def test_intersection_filtering_delivers_only_matching_events() -> None:
    subscribed_intersection_id = uuid.uuid4()
    other_intersection_id = uuid.uuid4()
    matching_event = RealtimeEventEnvelope(
        event=RealtimeEventName.SIGNAL_UPDATED,
        intersection_id=subscribed_intersection_id,
        data={"color": "green"},
    )
    non_matching_event = RealtimeEventEnvelope(
        event=RealtimeEventName.SIGNAL_UPDATED,
        intersection_id=other_intersection_id,
        data={"color": "red"},
    )
    websocket = FakeWebSocket()

    _connect(websocket, intersection_id=subscribed_intersection_id)
    non_matching_delivered = _run(realtime_event_publisher.publish(non_matching_event))
    matching_delivered = _run(realtime_event_publisher.publish(matching_event))
    message = websocket.sent[1]

    assert non_matching_delivered == 0
    assert matching_delivered == 1
    assert message["intersection_id"] == str(subscribed_intersection_id)


def test_event_name_filtering_delivers_only_matching_events() -> None:
    traffic_event = RealtimeEventEnvelope(event=RealtimeEventName.TRAFFIC_UPDATED)
    alert_event = RealtimeEventEnvelope(event=RealtimeEventName.ALERT_CREATED)
    websocket = FakeWebSocket()

    _connect(websocket, events=frozenset([RealtimeEventName.ALERT_CREATED]))
    traffic_delivered = _run(realtime_event_publisher.publish(traffic_event))
    alert_delivered = _run(realtime_event_publisher.publish(alert_event))
    message = websocket.sent[1]

    assert traffic_delivered == 0
    assert alert_delivered == 1
    assert message["event"] == RealtimeEventName.ALERT_CREATED.value


def test_disconnected_client_cleanup() -> None:
    websocket = FakeWebSocket()
    connection_id = _connect(websocket)
    assert websocket_manager.active_connection_count == 1

    websocket_manager.disconnect(connection_id)
    assert websocket_manager.active_connection_count == 0


def test_invalid_subscription_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        _parse_event_filter("not.supported")


def _connect(
    websocket: FakeWebSocket,
    *,
    intersection_id: uuid.UUID | None = None,
    events: frozenset[RealtimeEventName] | None = None,
) -> uuid.UUID:
    return _run(
        websocket_manager.connect(
            websocket,
            intersection_id=intersection_id,
            events=events,
        )
    )


def _run(awaitable):
    return asyncio.run(awaitable)
