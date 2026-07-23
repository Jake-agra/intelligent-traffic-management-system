import uuid


HEARTBEAT_TOPIC = "itms/v1/devices/{device_id}/heartbeat"
DEVICE_TELEMETRY_TOPIC = "itms/v1/devices/{device_id}/telemetry"
TRAFFIC_TOPIC = "itms/v1/intersections/{intersection_id}/traffic"
SIGNAL_COMMAND_TOPIC = "itms/v1/intersections/{intersection_id}/commands/signal"
SIGNAL_ACK_TOPIC = "itms/v1/intersections/{intersection_id}/commands/ack"
CONTROLLER_MODE_COMMAND_TOPIC = "itms/v1/intersections/{intersection_id}/commands/controller-mode"
CONTROLLER_STATUS_TOPIC = "itms/v1/intersections/{intersection_id}/controller/status"


def signal_command_topic(intersection_id: uuid.UUID) -> str:
    return SIGNAL_COMMAND_TOPIC.format(intersection_id=intersection_id)


def controller_mode_command_topic(intersection_id: uuid.UUID) -> str:
    return CONTROLLER_MODE_COMMAND_TOPIC.format(intersection_id=intersection_id)


def inbound_topics() -> list[str]:
    return [
        "itms/v1/devices/+/heartbeat",
        "itms/v1/devices/+/telemetry",
        "itms/v1/intersections/+/traffic",
        "itms/v1/intersections/+/commands/ack",
        "itms/v1/intersections/+/controller/status",
    ]


def topic_kind(topic: str) -> str | None:
    parts = topic.split("/")
    if len(parts) == 5 and parts[:3] == ["itms", "v1", "devices"]:
        if parts[4] == "heartbeat":
            return "heartbeat"
        if parts[4] == "telemetry":
            return "device_telemetry"
    if len(parts) == 5 and parts[:3] == ["itms", "v1", "intersections"]:
        if parts[4] == "traffic":
            return "traffic"
    if (
        len(parts) == 6
        and parts[:3] == ["itms", "v1", "intersections"]
        and parts[4] == "commands"
        and parts[5] == "ack"
    ):
        return "command_ack"
    if (
        len(parts) == 6
        and parts[:3] == ["itms", "v1", "intersections"]
        and parts[4] == "controller"
        and parts[5] == "status"
    ):
        return "controller_status"
    return None
