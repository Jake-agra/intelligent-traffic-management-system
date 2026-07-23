import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import type { Alert, DeviceHealth, Incident, SignalState, TrafficReading } from "../api/types";
import { canControlSignals, useAuth } from "../auth/AuthProvider";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { SignalBadge, StatusBadge } from "../components/StatusBadge";
import { useAsync } from "../components/useAsync";
import { SignalControlPanel } from "../features/intersections/SignalControlPanel";
import { useRealtime } from "../realtime/RealtimeProvider";

export function IntersectionDetailPage() {
  const { id } = useParams();
  const { api, user } = useAuth();
  const realtime = useRealtime();
  const live = useAsync(() => api.intersectionLive(id ?? ""), [api, id]);
  const reloadLive = live.reload;

  useEffect(() => {
    if (realtime.lastEvent?.intersection_id === id) {
      reloadLive();
    }
  }, [id, realtime.lastEvent, reloadLive]);

  if (!id) {
    return <ErrorState error={new Error("Intersection ID is missing.")} />;
  }
  if (live.isLoading) {
    return <LoadingState label="Loading intersection..." />;
  }
  if (live.error) {
    return <ErrorState error={live.error} />;
  }
  if (!live.data) {
    return <EmptyState title="No live state returned for this intersection." />;
  }

  const data = live.data;
  const currentSignalStates = latestSignalStatesForLanes(data.current_signal_states);
  return (
    <div className="page-grid">
      <section className="page-header">
        <div>
          <span className="eyebrow">Intersection detail</span>
          <h2>{data.intersection.name}</h2>
          <p>{data.intersection.location_description ?? "No location description provided."}</p>
        </div>
        <div className="header-stack">
          <Link className="button button--secondary" to={`/intersections/${id}/digital-twin`}>
            Digital Twin
          </Link>
          <StatusBadge label={data.intersection.is_active ? "active" : "inactive"} tone={data.intersection.is_active ? "good" : "neutral"} />
          <StatusBadge label={`WebSocket ${realtime.status}`} tone={realtime.status === "connected" ? "good" : "warning"} />
        </div>
      </section>

      <section className="stats-grid">
        <Stat label="Lanes" value={data.lanes.length} />
        <Stat label="Traffic readings" value={data.latest_traffic_readings.length} />
        <Stat label="Signals" value={currentSignalStates.length} />
        <Stat label="Devices" value={data.devices.length} />
        <Stat label="Last update" value={new Date(data.generated_at).toLocaleTimeString()} />
      </section>

      {canControlSignals(user) ? (
        <SignalControlPanel intersectionId={id} lanes={data.lanes} onSuccess={live.reload} />
      ) : null}

      <section className="content-grid">
        <Panel title="Lanes">
          <DataTable
            items={data.lanes}
            emptyLabel="No lanes configured."
            columns={[
              { header: "Name", render: (lane) => lane.name },
              { header: "Direction", render: (lane) => lane.direction },
              { header: "Status", render: (lane) => <StatusBadge label={lane.is_active ? "active" : "inactive"} tone={lane.is_active ? "good" : "neutral"} /> }
            ]}
          />
        </Panel>
        <Panel title="Current signal states">
          <DataTable<SignalState>
            items={currentSignalStates}
            emptyLabel="No current signal states."
            columns={[
              { header: "Lane", render: (state) => laneName(data.lanes, state.lane_id) },
              { header: "Signal", render: (state) => <SignalBadge color={state.color} /> },
              { header: "Mode", render: (state) => state.operating_mode },
              { header: "Ends", render: (state) => (state.ends_at ? new Date(state.ends_at).toLocaleTimeString() : "Open") }
            ]}
          />
        </Panel>
        <Panel title="Latest traffic readings">
          <DataTable<TrafficReading>
            items={data.latest_traffic_readings}
            emptyLabel="No traffic readings yet."
            columns={[
              { header: "Lane", render: (reading) => laneName(data.lanes, reading.lane_id) },
              { header: "Vehicles", render: (reading) => reading.vehicle_count },
              { header: "Density", render: (reading) => reading.density },
              { header: "Captured", render: (reading) => new Date(reading.captured_at).toLocaleTimeString() }
            ]}
          />
        </Panel>
        <Panel title="Connected devices">
          <DataTable<DeviceHealth>
            items={data.devices}
            emptyLabel="No connected devices."
            columns={[
              { header: "Name", render: (device) => device.name },
              { header: "Type", render: (device) => device.type },
              { header: "Status", render: (device) => <StatusBadge label={device.status} tone={device.status === "online" ? "good" : "danger"} /> }
            ]}
          />
        </Panel>
        <Panel title="Recent alerts">
          <DataTable<Alert>
            items={data.active_alerts}
            emptyLabel="No active alerts."
            columns={[
              { header: "Title", render: (alert) => alert.title },
              { header: "Severity", render: (alert) => alert.severity },
              { header: "Status", render: (alert) => alert.status }
            ]}
          />
        </Panel>
        <Panel title="Recent incidents">
          <DataTable<Incident>
            items={data.active_incidents}
            emptyLabel="No active incidents."
            columns={[
              { header: "Title", render: (incident) => incident.title },
              { header: "Status", render: (incident) => incident.status },
              { header: "Reported", render: (incident) => new Date(incident.reported_at).toLocaleString() }
            ]}
          />
        </Panel>
      </section>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <section className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

function laneName(lanes: { id: string; name: string }[], laneId: string | null): string {
  return lanes.find((lane) => lane.id === laneId)?.name ?? "Intersection";
}

function latestSignalStatesForLanes(states: SignalState[]): SignalState[] {
  const latest = new Map<string, SignalState>();
  for (const state of states) {
    const key = state.lane_id ?? "intersection";
    const current = latest.get(key);
    if (!current || isLaterSignalState(state, current)) {
      latest.set(key, state);
    }
  }
  return Array.from(latest.values()).sort((left, right) =>
    (right.started_at + right.id).localeCompare(left.started_at + left.id)
  );
}

function isLaterSignalState(candidate: SignalState, current: SignalState): boolean {
  if (candidate.started_at !== current.started_at) {
    return candidate.started_at > current.started_at;
  }
  return candidate.id > current.id;
}
