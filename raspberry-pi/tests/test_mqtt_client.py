import asyncio

from app.mqtt_client import FakeMQTTClient


def test_fake_mqtt_connection_and_subscription() -> None:
    client = FakeMQTTClient()

    asyncio.run(client.connect())
    asyncio.run(client.subscribe("itms/v1/intersections/example/commands/signal"))

    assert client.connected is True
    assert client.subscriptions == ["itms/v1/intersections/example/commands/signal"]
