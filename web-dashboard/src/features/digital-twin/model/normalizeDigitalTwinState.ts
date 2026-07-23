import type {
  DeviceStatus,
  IntersectionLiveState,
  RealtimeEventEnvelope,
  SignalColor
} from "../../../api/types";
import type {
  DigitalTwinViewModel,
  Direction,
  DirectionTwinState,
  TwinApiStatus,
  TwinDensity,
  TwinSignal
} from "../types";
import { DIRECTIONS } from "../types";

const STALE_AFTER_MS = 60_000;
const MAX_VISUAL_VEHICLES = 10;

export function normalizeDigitalTwinState({
  liveState,
  apiStatus = liveState ? "ok" : "no-data",
  websocketStatus,
  now = new Date()
}: {
  liveState: IntersectionLiveState | null;
  apiStatus?: TwinApiStatus;
  websocketStatus: string;
  now?: Date;
}): DigitalTwinViewModel {
  const directions = Object.fromEntries(
    DIRECTIONS.map((direction) => [direction, emptyDirection(direction)])
  ) as Record<Direction, DirectionTwinState>;

  if (!liveState) {
    return {
      intersectionId: "",
      intersectionName: "Unknown intersection",
      apiStatus,
      websocketStatus,
      lastUpdateAt: null,
      isStale: true,
      directions,
      deviceStatusSummary: { online: 0, offline: 0, degraded: 0 },
      controllerState: null,
      staleReason: "No live intersection state has been loaded."
    };
  }

  const lanesByDirection = new Map<Direction, (typeof liveState.lanes)[number]>();
  for (const lane of liveState.lanes) {
    const direction = normalizeDirection(lane.direction);
    if (direction && !lanesByDirection.has(direction)) {
      lanesByDirection.set(direction, lane);
    }
  }

  const latestSignalByLane = latestByLane(liveState.current_signal_states, "started_at");
  const latestTrafficByLane = latestByLane(liveState.latest_traffic_readings, "captured_at");

  for (const direction of DIRECTIONS) {
    const lane = lanesByDirection.get(direction);
    if (!lane) {
      directions[direction] = emptyDirection(direction, "missing-lane");
      continue;
    }

    const signalState = latestSignalByLane.get(lane.id);
    const trafficReading = latestTrafficByLane.get(lane.id);
    const signal = normalizeSignal(signalState?.color);
    const density = normalizeDensity(trafficReading?.density);
    directions[direction] = {
      direction,
      laneId: lane.id,
      laneName: lane.name,
      signal,
      density,
      vehicleCount: trafficReading?.vehicle_count ?? null,
      visualVehicleCount: vehicleVisualCount(density, trafficReading?.vehicle_count ?? null),
      lastTrafficAt: trafficReading?.captured_at ?? null,
      lastSignalAt: signalState?.started_at ?? null,
      mappingStatus: signalState
        ? signal === "unknown"
          ? "unknown-signal"
          : "mapped"
        : "missing-signal"
    };
  }

  const lastUpdateAt = latestTimestamp([
    liveState.generated_at,
    ...liveState.current_signal_states.map((state) => state.started_at),
    ...liveState.latest_traffic_readings.map((reading) => reading.captured_at)
  ]);
  const ageMs = lastUpdateAt ? now.getTime() - new Date(lastUpdateAt).getTime() : Infinity;
  const isStale = !lastUpdateAt || ageMs > STALE_AFTER_MS || websocketStatus !== "connected";

  return {
    intersectionId: liveState.intersection.id,
    intersectionName: liveState.intersection.name,
    apiStatus,
    websocketStatus,
    lastUpdateAt,
    isStale,
    directions,
    deviceStatusSummary: summarizeDevices(liveState.devices),
    controllerState: liveState.controller_state,
    staleReason: staleReason({ lastUpdateAt, ageMs, websocketStatus })
  };
}

export function normalizeSignal(value: unknown): TwinSignal {
  return value === "red" || value === "yellow" || value === "green" ? value : "unknown";
}

export function normalizeDirection(value: unknown): Direction | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return DIRECTIONS.includes(normalized as Direction) ? (normalized as Direction) : null;
}

export function normalizeDensity(value: unknown): TwinDensity {
  return value === "low" || value === "medium" || value === "high" ? value : "unknown";
}

export function vehicleVisualCount(
  density: TwinDensity,
  vehicleCount: number | null,
): number {
  if (density === "unknown" || vehicleCount === null) {
    return 0;
  }
  return Math.min(MAX_VISUAL_VEHICLES, Math.max(0, vehicleCount));
}

export function isDigitalTwinRealtimeEvent(event: RealtimeEventEnvelope): boolean {
  return (
    event.event === "signal.updated" ||
    event.event === "traffic.updated" ||
    event.event === "device.status_changed" ||
    event.event === "controller.mode_updated" ||
    event.event === "incident.updated" ||
    event.event === "incident.created"
  );
}

function emptyDirection(
  direction: Direction,
  mappingStatus: DirectionTwinState["mappingStatus"] = "missing-lane"
): DirectionTwinState {
  return {
    direction,
    laneId: null,
    laneName: direction,
    signal: "unknown",
    density: "unknown",
    vehicleCount: null,
    visualVehicleCount: 0,
    lastTrafficAt: null,
    lastSignalAt: null,
    mappingStatus
  };
}

function latestByLane<T extends { id: string; lane_id: string | null }>(
  items: T[],
  timestampKey: keyof T
): Map<string, T> {
  const latest = new Map<string, T>();
  for (const item of items) {
    if (!item.lane_id) {
      continue;
    }
    const current = latest.get(item.lane_id);
    if (!current || isLaterAuthoritative(item, current, timestampKey)) {
      latest.set(item.lane_id, item);
    }
  }
  return latest;
}

function isLaterAuthoritative<T extends { id: string }>(
  candidate: T,
  current: T,
  timestampKey: keyof T
): boolean {
  const candidateTimestamp = String(candidate[timestampKey]);
  const currentTimestamp = String(current[timestampKey]);
  if (candidateTimestamp !== currentTimestamp) {
    return candidateTimestamp > currentTimestamp;
  }
  return candidate.id > current.id;
}

function latestTimestamp(values: (string | null)[]): string | null {
  const timestamps = values.filter(Boolean) as string[];
  if (timestamps.length === 0) {
    return null;
  }
  return timestamps.sort().at(-1) ?? null;
}

function summarizeDevices(
  devices: { status: DeviceStatus }[]
): Record<DeviceStatus, number> {
  return devices.reduce(
    (summary, device) => {
      summary[device.status] += 1;
      return summary;
    },
    { online: 0, offline: 0, degraded: 0 } as Record<DeviceStatus, number>
  );
}

function staleReason({
  lastUpdateAt,
  ageMs,
  websocketStatus
}: {
  lastUpdateAt: string | null;
  ageMs: number;
  websocketStatus: string;
}): string | null {
  if (!lastUpdateAt) {
    return "No backend update timestamp is available.";
  }
  if (websocketStatus !== "connected") {
    return "WebSocket is not connected; refresh current state before trusting live changes.";
  }
  if (ageMs > STALE_AFTER_MS) {
    return "Backend live data is older than one minute.";
  }
  return null;
}

export const digitalTwinModelLimits = {
  maxVisualVehicles: MAX_VISUAL_VEHICLES,
  staleAfterMs: STALE_AFTER_MS
};

export type { SignalColor };
