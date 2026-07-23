import { useMemo } from "react";
import { Link } from "react-router-dom";
import type { Alert, DeviceHealth, Incident, SignalState } from "../api/types";
import { canViewDashboard, useAuth } from "../auth/AuthProvider";
import { EmptyState, ErrorState, isUnauthorized, LoadingState, UnauthorizedState } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { StatCard } from "../components/StatCard";
import { SignalBadge, StatusBadge } from "../components/StatusBadge";
import { useAsync } from "../components/useAsync";
import { useRealtime } from "../realtime/RealtimeProvider";

export function OverviewPage() {
  const { api, user } = useAuth();
  const realtime = useRealtime();
  const health = useAsync(() => api.health(), [api]);
  const summary = useAsync(() => api.dashboardSummary(), [api]);
  const intersections = useAsync(() => api.intersections(), [api]);
  const alerts = useAsync(() => api.alerts({ limit: 5 }), [api]);
  const incidents = useAsync(() => api.incidents({ limit: 5 }), [api]);
  const devices = useAsync(() => api.devices({ limit: 50 }), [api]);

  const visibleSignals = useMemo<SignalState[]>(() => [], []);

  if (!canViewDashboard(user)) {
    return <UnauthorizedState />;
  }

  if (summary.isLoading) {
    return <LoadingState label="Loading dashboard summary..." />;
  }
  if (summary.error) {
    return isUnauthorized(summary.error) ? <UnauthorizedState /> : <ErrorState error={summary.error} />;
  }
  const data = summary.data;
  if (!data) {
    return <EmptyState title="No dashboard summary available." />;
  }

  return (
    <div className="page-grid">
      <section className="page-header">
        <div>
          <span className="eyebrow">Overview</span>
          <h2>Network status</h2>
        </div>
        <StatusBadge
          label={`API ${health.data?.api_status ?? (health.error ? "unavailable" : "checking")}`}
          tone={health.data?.api_status === "ok" ? "good" : "warning"}
        />
      </section>

      <section className="stats-grid">
        <StatCard label="Total intersections" value={data.intersections.total ?? 0} />
        <StatCard label="Active incidents" value={data.incidents.active ?? 0} />
        <StatCard label="Unresolved alerts" value={data.alerts.active ?? 0} />
        <StatCard label="Recent violations" value={data.violations.recent ?? 0} />
        <StatCard label="Online devices" value={data.devices.online ?? 0} />
        <StatCard label="Offline devices" value={data.devices.offline ?? 0} />
        <StatCard label="WebSocket" value={realtime.status} />
        <StatCard label="Backend database" value={health.data?.database_status ?? "unknown"} />
      </section>

      <div className="content-grid">
        <section className="panel">
          <h3>Recent alerts</h3>
          <ResourceList
            loading={alerts.isLoading}
            error={alerts.error}
            items={alerts.data?.items ?? []}
            empty="No active alerts."
            render={(alert: Alert) => (
              <div className="list-row">
                <strong>{alert.title}</strong>
                <StatusBadge label={alert.severity} tone={alert.severity === "critical" ? "danger" : "warning"} />
              </div>
            )}
          />
        </section>

        <section className="panel">
          <h3>Recent incidents</h3>
          <ResourceList
            loading={incidents.isLoading}
            error={incidents.error}
            items={incidents.data?.items ?? []}
            empty="No active incidents."
            render={(incident: Incident) => (
              <div className="list-row">
                <strong>{incident.title}</strong>
                <StatusBadge label={incident.status} tone={incident.status === "open" ? "warning" : "neutral"} />
              </div>
            )}
          />
        </section>

        <section className="panel">
          <h3>Current intersection signal states</h3>
          {visibleSignals.length === 0 ? (
            <EmptyState title="No signal states returned by the overview endpoint." />
          ) : (
            visibleSignals.map((signal) => <SignalBadge key={signal.id} color={signal.color} />)
          )}
        </section>

        <section className="panel">
          <h3>Device health summary</h3>
          <ResourceList
            loading={devices.isLoading}
            error={devices.error}
            items={devices.data?.items ?? []}
            empty="No devices registered."
            render={(device: DeviceHealth) => (
              <div className="list-row">
                <span>{device.name}</span>
                <StatusBadge label={device.status} tone={device.status === "online" ? "good" : "danger"} />
              </div>
            )}
          />
        </section>
      </div>

      <section className="panel">
        <h3>Intersections</h3>
        <DataTable
          items={intersections.data ?? []}
          emptyLabel="No intersections found."
          columns={[
            { header: "Name", render: (item) => <Link to={`/intersections/${item.id}`}>{item.name}</Link> },
            { header: "Status", render: (item) => <StatusBadge label={item.is_active ? "active" : "inactive"} tone={item.is_active ? "good" : "neutral"} /> },
            { header: "Location", render: (item) => item.location_description ?? "Unspecified" }
          ]}
        />
      </section>
    </div>
  );
}

function ResourceList<T>({
  loading,
  error,
  items,
  empty,
  render
}: {
  loading: boolean;
  error: unknown;
  items: T[];
  empty: string;
  render(item: T): React.ReactNode;
}) {
  if (loading) {
    return <LoadingState />;
  }
  if (error) {
    return isUnauthorized(error) ? <UnauthorizedState /> : <ErrorState error={error} />;
  }
  if (items.length === 0) {
    return <EmptyState title={empty} />;
  }
  return <div className="list-stack">{items.map((item, index) => <div key={index}>{render(item)}</div>)}</div>;
}
