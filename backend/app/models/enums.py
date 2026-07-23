from enum import Enum
from typing import TypeVar


EnumType = TypeVar("EnumType", bound=Enum)


def enum_values(enum_type: type[EnumType]) -> list[str]:
    return [str(member.value) for member in enum_type]


class UserRole(str, Enum):
    ADMIN = "admin"
    POLICE = "police"
    ANALYST = "analyst"
    EMERGENCY_RESPONDER = "emergency_responder"


class TrafficDensity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SignalColor(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class OperatingMode(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    FAILSAFE = "failsafe"


class DeviceType(str, Enum):
    CAMERA = "camera"
    RASPBERRY_PI = "raspberry_pi"
    TRAFFIC_LIGHT = "traffic_light"
    BUZZER = "buzzer"
    MQTT_GATEWAY = "mqtt_gateway"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class SignalEventSource(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    EMERGENCY = "emergency"
    SIMULATION = "simulation"
    PHYSICAL = "physical"
