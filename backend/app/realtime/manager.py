from dataclasses import dataclass
import uuid

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.schemas.realtime import (
    ConnectionAckEnvelope,
    RealtimeEventEnvelope,
    RealtimeEventName,
    SubscriptionResponse,
)


@dataclass(frozen=True)
class ClientSubscription:
    connection_id: uuid.UUID
    websocket: WebSocket
    intersection_id: uuid.UUID | None
    events: frozenset[RealtimeEventName] | None

    def matches(self, event: RealtimeEventEnvelope) -> bool:
        if self.intersection_id is not None and event.intersection_id != self.intersection_id:
            return False
        if self.events is not None and event.event not in self.events:
            return False
        return True


class WebSocketConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, ClientSubscription] = {}

    @property
    def active_connection_count(self) -> int:
        return len(self._connections)

    async def connect(
        self,
        websocket: WebSocket,
        *,
        intersection_id: uuid.UUID | None,
        events: frozenset[RealtimeEventName] | None,
    ) -> uuid.UUID:
        await websocket.accept()
        connection_id = uuid.uuid4()
        self._connections[connection_id] = ClientSubscription(
            connection_id=connection_id,
            websocket=websocket,
            intersection_id=intersection_id,
            events=events,
        )
        await websocket.send_json(
            ConnectionAckEnvelope(
                connection_id=connection_id,
                subscription=SubscriptionResponse(
                    intersection_id=intersection_id,
                    events=sorted(events, key=lambda event: event.value) if events else None,
                ),
                supported_events=list(RealtimeEventName),
            ).model_dump(mode="json")
        )
        return connection_id

    def disconnect(self, connection_id: uuid.UUID) -> None:
        self._connections.pop(connection_id, None)

    async def broadcast(self, event: RealtimeEventEnvelope) -> int:
        delivered = 0
        stale_connections: list[uuid.UUID] = []
        for connection_id, subscription in list(self._connections.items()):
            if not subscription.matches(event):
                continue
            try:
                await subscription.websocket.send_json(event.model_dump(mode="json"))
                delivered += 1
            except (RuntimeError, WebSocketDisconnect):
                stale_connections.append(connection_id)

        for connection_id in stale_connections:
            self.disconnect(connection_id)

        return delivered

    def reset(self) -> None:
        self._connections.clear()


websocket_manager = WebSocketConnectionManager()
