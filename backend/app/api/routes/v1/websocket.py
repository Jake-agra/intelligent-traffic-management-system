import uuid

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.realtime import websocket_manager
from app.schemas.realtime import HeartbeatEnvelope, RealtimeEventName


router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    try:
        intersection_id = _parse_intersection_id(
            websocket.query_params.get("intersection_id")
        )
        events = _parse_event_filter(websocket.query_params.get("events"))
    except ValueError:
        await websocket.close(code=1008)
        return

    connection_id = await websocket_manager.connect(
        websocket,
        intersection_id=intersection_id,
        events=events,
    )
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json(
                    HeartbeatEnvelope(type="pong").model_dump(mode="json")
                )
    except WebSocketDisconnect:
        websocket_manager.disconnect(connection_id)


def _parse_intersection_id(value: str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return uuid.UUID(value)


def _parse_event_filter(value: str | None) -> frozenset[RealtimeEventName] | None:
    if value is None or value.strip() == "":
        return None

    event_names = []
    for raw_event in value.split(","):
        event_name = raw_event.strip()
        if not event_name:
            continue
        event_names.append(RealtimeEventName(event_name))

    if not event_names:
        return None
    return frozenset(event_names)
