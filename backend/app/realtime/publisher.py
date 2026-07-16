from app.realtime.manager import WebSocketConnectionManager, websocket_manager
from app.schemas.realtime import RealtimeEventEnvelope


class RealtimeEventPublisher:
    def __init__(self, manager: WebSocketConnectionManager) -> None:
        self._manager = manager

    async def publish(self, event: RealtimeEventEnvelope) -> int:
        return await self._manager.broadcast(event)


realtime_event_publisher = RealtimeEventPublisher(websocket_manager)
