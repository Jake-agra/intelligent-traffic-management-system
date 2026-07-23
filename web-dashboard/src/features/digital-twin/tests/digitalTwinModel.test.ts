import { describe, expect, it } from "vitest";
import type { IntersectionLiveState, RealtimeEventEnvelope } from "../../../api/types";
import { shouldRefreshDigitalTwin } from "../model/applyRealtimeEvent";
import {
  digitalTwinModelLimits,
  normalizeDigitalTwinState,
  normalizeSignal,
  vehicleVisualCount
} from "../model/normalizeDigitalTwinState";

const intersectionId = "00000000-0000-0000-0000-000000000002";

describe("digital twin model", () => {
  it("maps configured lanes to four directions", () => {
    const model = normalizeDigitalTwinState({
      liveState: liveState(),
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(model.directions.north.laneName).toBe("Northbound");
    expect(model.directions.south.laneName).toBe("Southbound");
    expect(model.directions.east.laneName).toBe("Eastbound");
    expect(model.directions.west.laneName).toBe("Westbound");
  });

  it("normalizes red yellow green and unknown signals", () => {
    expect(normalizeSignal("red")).toBe("red");
    expect(normalizeSignal("yellow")).toBe("yellow");
    expect(normalizeSignal("green")).toBe("green");
    expect(normalizeSignal("flashing-blue")).toBe("unknown");
  });

  it("marks missing lanes and missing signals as unknown", () => {
    const state = liveState();
    state.lanes = state.lanes.filter((lane) => lane.direction !== "west");
    state.current_signal_states = state.current_signal_states.filter(
      (signal) => signal.lane_id !== "lane-east"
    );

    const model = normalizeDigitalTwinState({
      liveState: state,
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(model.directions.west.signal).toBe("unknown");
    expect(model.directions.west.mappingStatus).toBe("missing-lane");
    expect(model.directions.east.signal).toBe("unknown");
    expect(model.directions.east.mappingStatus).toBe("missing-signal");
  });

  it("normalizes traffic density and caps vehicle visuals", () => {
    const model = normalizeDigitalTwinState({
      liveState: liveState({ northVehicles: 99, northDensity: "high" }),
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(model.directions.north.density).toBe("high");
    expect(model.directions.north.visualVehicleCount).toBe(
      digitalTwinModelLimits.maxVisualVehicles
    );
    expect(vehicleVisualCount("unknown", null)).toBe(0);
  });

  it("uses zero visual vehicles when traffic readings are missing", () => {
    const state = liveState();
    state.latest_traffic_readings = [];

    const model = normalizeDigitalTwinState({
      liveState: state,
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(model.directions.north.vehicleCount).toBeNull();
    expect(model.directions.north.visualVehicleCount).toBe(0);
    expect(model.directions.south.visualVehicleCount).toBe(0);
  });

  it("derives bounded vehicle visuals from seeded traffic readings", () => {
    const model = normalizeDigitalTwinState({
      liveState: liveState({ northVehicles: 7, northDensity: "medium" }),
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(model.directions.north.vehicleCount).toBe(7);
    expect(model.directions.north.visualVehicleCount).toBe(7);
    expect(vehicleVisualCount("medium", 99)).toBe(digitalTwinModelLimits.maxVisualVehicles);
  });

  it("selects the latest signal state from duplicate lane history", () => {
    const state = liveState();
    state.current_signal_states = [
      signal("lane-north", "red", "2026-07-22T00:00:01Z", "signal-a"),
      signal("lane-north", "green", "2026-07-22T00:00:02Z", "signal-b"),
      signal("lane-south", "red", "2026-07-22T00:00:02Z", "signal-c"),
      signal("lane-south", "yellow", "2026-07-22T00:00:02Z", "signal-d")
    ];

    const model = normalizeDigitalTwinState({
      liveState: state,
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(model.directions.north.signal).toBe("green");
    expect(model.directions.south.signal).toBe("yellow");
  });

  it("marks old or disconnected data as stale", () => {
    const old = normalizeDigitalTwinState({
      liveState: liveState(),
      websocketStatus: "connected",
      now: new Date("2026-07-22T00:03:00Z")
    });
    const disconnected = normalizeDigitalTwinState({
      liveState: liveState(),
      websocketStatus: "disconnected",
      now: new Date("2026-07-22T00:00:10Z")
    });

    expect(old.isStale).toBe(true);
    expect(disconnected.isStale).toBe(true);
  });

  it("accepts relevant matching realtime events and rejects duplicates", () => {
    const seen = new Set<string>();
    const event = realtimeEvent("signal.updated", "event-1");

    expect(shouldRefreshDigitalTwin(event, intersectionId, seen)).toEqual({
      shouldRefresh: true,
      reason: "signal.updated"
    });
    expect(shouldRefreshDigitalTwin(event, intersectionId, seen)).toEqual({
      shouldRefresh: false,
      reason: "duplicate"
    });
  });

  it("ignores realtime events for other intersections", () => {
    const decision = shouldRefreshDigitalTwin(
      { ...realtimeEvent("traffic.updated", "event-2"), intersection_id: "other" },
      intersectionId,
      new Set<string>()
    );

    expect(decision).toEqual({ shouldRefresh: false, reason: "other-intersection" });
  });
});

function liveState({
  northVehicles = 4,
  northDensity = "medium"
}: {
  northVehicles?: number;
  northDensity?: "low" | "medium" | "high";
} = {}): IntersectionLiveState {
  return {
    intersection: {
      id: intersectionId,
      name: "Central Junction",
      location_description: "Main road",
      latitude: null,
      longitude: null,
      is_active: true,
      created_at: "2026-07-22T00:00:00Z",
      updated_at: "2026-07-22T00:00:00Z"
    },
    lanes: [
      lane("lane-north", "Northbound", "north", 1),
      lane("lane-south", "Southbound", "south", 2),
      lane("lane-east", "Eastbound", "east", 3),
      lane("lane-west", "Westbound", "west", 4)
    ],
    latest_traffic_readings: [
      traffic("lane-north", northVehicles, northDensity),
      traffic("lane-south", 1, "low"),
      traffic("lane-east", 6, "medium"),
      traffic("lane-west", 8, "high")
    ],
    current_signal_states: [
      signal("lane-north", "green"),
      signal("lane-south", "green"),
      signal("lane-east", "red"),
      signal("lane-west", "red")
    ],
    active_incidents: [],
    recent_violations: [],
    active_alerts: [],
    devices: [],
    generated_at: "2026-07-22T00:00:00Z"
  };
}

function lane(id: string, name: string, direction: string, sequence: number) {
  return {
    id,
    intersection_id: intersectionId,
    name,
    direction,
    sequence,
    is_active: true,
    created_at: "2026-07-22T00:00:00Z",
    updated_at: "2026-07-22T00:00:00Z"
  };
}

function signal(
  laneId: string,
  color: "red" | "yellow" | "green",
  startedAt = "2026-07-22T00:00:00Z",
  id = `signal-${laneId}`
) {
  return {
    id,
    intersection_id: intersectionId,
    lane_id: laneId,
    color,
    operating_mode: "manual" as const,
    started_at: startedAt,
    ends_at: null
  };
}

function traffic(laneId: string, vehicleCount: number, density: "low" | "medium" | "high") {
  return {
    id: `traffic-${laneId}`,
    intersection_id: intersectionId,
    lane_id: laneId,
    device_id: null,
    vehicle_count: vehicleCount,
    density,
    captured_at: "2026-07-22T00:00:00Z"
  };
}

function realtimeEvent(
  event: RealtimeEventEnvelope["event"],
  eventId: string
): RealtimeEventEnvelope {
  return {
    event,
    event_id: eventId,
    version: 1,
    occurred_at: "2026-07-22T00:00:00Z",
    intersection_id: intersectionId,
    data: {}
  };
}
