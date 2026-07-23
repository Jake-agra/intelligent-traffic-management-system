import asyncio
import sys
from types import ModuleType
from types import SimpleNamespace

from app.mqtt.client import PahoMQTTClient


def test_paho_disconnect_is_bounded(monkeypatch) -> None:
    paho = ModuleType("paho")
    paho_mqtt = ModuleType("paho.mqtt")
    paho_client = ModuleType("paho.mqtt.client")
    paho_client.CallbackAPIVersion = SimpleNamespace(VERSION2=2)
    paho_client.Client = SlowPahoClient
    monkeypatch.setitem(sys.modules, "paho", paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", paho_mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", paho_client)
    client = PahoMQTTClient(
        SimpleNamespace(
            mqtt_client_id="test-client",
            mqtt_username=None,
            mqtt_password=None,
            mqtt_tls_enabled=False,
            mqtt_disconnect_timeout_seconds=0.01,
        )
    )

    asyncio.run(client.disconnect())


class SlowPahoClient:
    def __init__(self, *_args, **_kwargs) -> None:
        self.on_connect = None
        self.on_message = None

    def disconnect(self) -> None:
        import time

        time.sleep(0.05)

    def loop_stop(self) -> None:
        import time

        time.sleep(0.05)
