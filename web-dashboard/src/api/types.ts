export type UserRole = "admin" | "police" | "analyst" | "emergency_responder";
export type SignalColor = "red" | "yellow" | "green";
export type OperatingMode = "automatic" | "manual" | "failsafe";
export type DeviceStatus = "online" | "offline" | "degraded";
export type AlertStatus = "open" | "acknowledged" | "resolved";
export type AlertSeverity = "info" | "warning" | "critical";
export type IncidentStatus = "open" | "investigating" | "resolved";
export type TrafficDensity = "low" | "medium" | "high";

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserProfile;
}

export interface HealthResponse {
  service_name: string;
  api_version: string;
  environment: string;
  api_status: string;
  database_status: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Lane {
  id: string;
  intersection_id: string;
  name: string;
  direction: string;
  sequence: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntersectionSummary {
  id: string;
  name: string;
  location_description: string | null;
  latitude: number | null;
  longitude: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntersectionDetail extends IntersectionSummary {
  lanes: Lane[];
}

export interface TrafficReading {
  id: string;
  intersection_id: string;
  lane_id: string | null;
  device_id: string | null;
  vehicle_count: number;
  density: TrafficDensity;
  captured_at: string;
}

export interface SignalState {
  id: string;
  intersection_id: string;
  lane_id: string | null;
  color: SignalColor;
  operating_mode: OperatingMode;
  started_at: string;
  ends_at: string | null;
}

export interface ControllerState {
  id: string;
  intersection_id: string;
  device_id: string | null;
  mode: OperatingMode;
  requested_mode: OperatingMode | null;
  command_status: string;
  command_id: string | null;
  phase: string | null;
  phase_started_at: string | null;
  phase_duration_seconds: number | null;
  next_phase: string | null;
  reason: string | null;
  message: string | null;
  confirmed_at: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Alert {
  id: string;
  intersection_id: string;
  lane_id: string | null;
  device_id: string | null;
  incident_id: string | null;
  title: string;
  message: string | null;
  severity: AlertSeverity;
  status: AlertStatus;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface Incident {
  id: string;
  intersection_id: string;
  lane_id: string | null;
  device_id: string | null;
  title: string;
  description: string | null;
  status: IncidentStatus;
  reported_at: string;
  resolved_at: string | null;
}

export interface Violation {
  id: string;
  intersection_id: string;
  lane_id: string | null;
  device_id: string | null;
  violation_type: string;
  evidence_uri: string | null;
  occurred_at: string;
}

export interface DeviceHealth {
  id: string;
  intersection_id: string;
  lane_id: string | null;
  identifier: string;
  name: string;
  type: string;
  status: DeviceStatus;
  last_seen_at: string | null;
}

export interface IntersectionLiveState {
  intersection: IntersectionSummary;
  lanes: Lane[];
  latest_traffic_readings: TrafficReading[];
  current_signal_states: SignalState[];
  active_incidents: Incident[];
  recent_violations: Violation[];
  active_alerts: Alert[];
  devices: DeviceHealth[];
  controller_state: ControllerState | null;
  generated_at: string;
}

export interface DashboardSummary {
  generated_at: string;
  intersections: Record<string, number>;
  traffic: Record<string, number | string | null>;
  signals: Record<string, number>;
  incidents: Record<string, number>;
  violations: Record<string, number>;
  alerts: Record<string, number>;
  devices: Record<string, number>;
}

export interface SignalModeResponse {
  action: string;
  audit_log_id: string;
  emitted_event: string;
  intersection_id: string;
  mode: OperatingMode;
  reason: string;
  status: string;
  command_id: string | null;
}

export interface SignalOverrideResponse {
  action: string;
  audit_log_id: string;
  emitted_event: string;
  intersection_id: string;
  lane_id: string;
  color: SignalColor;
  duration_seconds: number;
  started_at: string;
  ends_at: string;
  signal_event_id: string | null;
  command_id: string | null;
}

export type RealtimeEventName =
  | "traffic.updated"
  | "signal.updated"
  | "violation.created"
  | "incident.created"
  | "incident.updated"
  | "alert.created"
  | "alert.acknowledged"
  | "device.status_changed"
  | "controller.mode_updated";

export interface RealtimeEventEnvelope {
  event: RealtimeEventName;
  version: number;
  event_id: string;
  occurred_at: string;
  intersection_id: string | null;
  data: Record<string, unknown>;
}
