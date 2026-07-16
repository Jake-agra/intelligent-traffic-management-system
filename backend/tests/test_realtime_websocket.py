import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.realtime import realtime_event_publisher, websocket_manager
from app.schemas.realtime import RealtimeEventEnvelope, RealtimeEventName


@pytest.fixture(autouse=True)
def reset_websocket_manager() -> None:
    websocket_manager.reset()


def test_websocket_sends_connection_acknowledgement(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "connection.acknowledged"
    assert message["version"] == 1
    assert message["subscription"] == {"intersection_id": None, "events": None}
    assert RealtimeEventName.TRAFFIC_UPDATED.value in message["supported_events"]


def test_event_broadcast_reaches_two_clients(client: TestClient) -> None:
    event = RealtimeEventEnvelope(
        event=RealtimeEventName.TRAFFIC_UPDATED,
        data={"vehicle_count": 8},
    )

    with client.websocket_connect("/api/v1/ws") as first:
        first.receive_json()
        with client.websocket_connect("/api/v1/ws") as second:
            second.receive_json()

            delivered = client.portal.call(realtime_event_publisher.publish, event)

            assert delivered == 2
            assert first.receive_json()["event"] == RealtimeEventName.TRAFFIC_UPDATED.value
            assert second.receive_json()["event"] == RealtimeEventName.TRAFFIC_UPDATED.value


def test_intersection_filtering_delivers_only_matching_events(
    client: TestClient,
) -> None:
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

    with client.websocket_connect(
        f"/api/v1/ws?intersection_id={subscribed_intersection_id}"
    ) as websocket:
        websocket.receive_json()

        non_matching_delivered = client.portal.call(
            realtime_event_publisher.publish,
            non_matching_event,
        )
        matching_delivered = client.portal.call(
            realtime_event_publisher.publish,
            matching_event,
        )

        message = websocket.receive_json()

    assert non_matching_delivered == 0
    assert matching_delivered == 1
    assert message["intersection_id"] == str(subscribed_intersection_id)


def test_event_name_filtering_delivers_only_matching_events(
    client: TestClient,
) -> None:
    traffic_event = RealtimeEventEnvelope(event=RealtimeEventName.TRAFFIC_UPDATED)
    alert_event = RealtimeEventEnvelope(event=RealtimeEventName.ALERT_CREATED)

    with client.websocket_connect(
        f"/api/v1/ws?events={RealtimeEventName.ALERT_CREATED.value}"
    ) as websocket:
        websocket.receive_json()

        traffic_delivered = client.portal.call(
            realtime_event_publisher.publish,
            traffic_event,
        )
        alert_delivered = client.portal.call(
            realtime_event_publisher.publish,
            alert_event,
        )

        message = websocket.receive_json()

    assert traffic_delivered == 0
    assert alert_delivered == 1
    assert message["event"] == RealtimeEventName.ALERT_CREATED.value


def test_disconnected_client_cleanup(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.receive_json()
        assert websocket_manager.active_connection_count == 1

    assert websocket_manager.active_connection_count == 0


def test_invalid_subscription_input_is_rejected(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws?events=not.supported") as websocket:
            websocket.receive_json()
