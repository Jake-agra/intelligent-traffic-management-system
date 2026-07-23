import type { DeviceStatus, TrafficDensity } from "../../../api/types";

export const DIRECTIONS = ["north", "south", "east", "west"] as const;

export type Direction = (typeof DIRECTIONS)[number];
export type TwinSignal = "red" | "yellow" | "green" | "unknown";
export type TwinDensity = TrafficDensity | "unknown";
export type MappingStatus = "mapped" | "missing-lane" | "missing-signal" | "unknown-signal";
export type TwinApiStatus = "loading" | "ok" | "error" | "no-data";

export interface DirectionTwinState {
  direction: Direction;
  laneId: string | null;
  laneName: string;
  signal: TwinSignal;
  density: TwinDensity;
  vehicleCount: number | null;
  visualVehicleCount: number;
  lastTrafficAt: string | null;
  lastSignalAt: string | null;
  mappingStatus: MappingStatus;
}

export interface DigitalTwinViewModel {
  intersectionId: string;
  intersectionName: string;
  apiStatus: TwinApiStatus;
  websocketStatus: string;
  lastUpdateAt: string | null;
  isStale: boolean;
  directions: Record<Direction, DirectionTwinState>;
  deviceStatusSummary: Record<DeviceStatus, number>;
  staleReason: string | null;
}
