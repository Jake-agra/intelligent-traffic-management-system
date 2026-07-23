import type { Alert, DeviceHealth, Incident, Violation } from "../api/types";
import {
  canViewDevices,
  canViewIncidents,
  canViewViolations,
  useAuth
} from "../auth/AuthProvider";
import {
  EmptyState,
  ErrorState,
  isUnauthorized,
  LoadingState,
  UnauthorizedState
} from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { useAsync } from "../components/useAsync";

export function AlertsPage() {
  const { api } = useAuth();
  const alerts = useAsync(() => api.alerts({ limit: 50 }), [api]);

  return (
    <ResourcePage
      title="Alerts"
      eyebrow="Operations"
      loading={alerts.isLoading}
      error={alerts.error}
      empty={!alerts.data || alerts.data.items.length === 0}
      emptyTitle="No alerts returned by the backend."
    >
      <DataTable<Alert>
        items={alerts.data?.items ?? []}
        emptyLabel="No alerts returned by the backend."
        columns={[
          { header: "Title", render: (alert) => alert.title },
          { header: "Severity", render: (alert) => <StatusBadge label={alert.severity} tone={alert.severity === "critical" ? "danger" : "warning"} /> },
          { header: "Status", render: (alert) => alert.status },
          { header: "Message", render: (alert) => alert.message ?? "No message" }
        ]}
      />
    </ResourcePage>
  );
}

export function IncidentsPage() {
  const { api, user } = useAuth();
  const incidents = useAsync(() => api.incidents({ limit: 50 }), [api]);

  if (!canViewIncidents(user)) {
    return <UnauthorizedState />;
  }
  return (
    <ResourcePage
      title="Incidents"
      eyebrow="Response"
      loading={incidents.isLoading}
      error={incidents.error}
      empty={!incidents.data || incidents.data.items.length === 0}
      emptyTitle="No incidents returned by the backend."
    >
      <DataTable<Incident>
        items={incidents.data?.items ?? []}
        emptyLabel="No incidents returned by the backend."
        columns={[
          { header: "Title", render: (incident) => incident.title },
          { header: "Status", render: (incident) => <StatusBadge label={incident.status} tone={incident.status === "open" ? "warning" : "neutral"} /> },
          { header: "Description", render: (incident) => incident.description ?? "No description" },
          { header: "Reported", render: (incident) => new Date(incident.reported_at).toLocaleString() }
        ]}
      />
    </ResourcePage>
  );
}

export function ViolationsPage() {
  const { api, user } = useAuth();
  const violations = useAsync(() => api.violations({ limit: 50 }), [api]);

  if (!canViewViolations(user)) {
    return <UnauthorizedState />;
  }
  return (
    <ResourcePage
      title="Violations"
      eyebrow="Enforcement"
      loading={violations.isLoading}
      error={violations.error}
      empty={!violations.data || violations.data.items.length === 0}
      emptyTitle="No violations returned by the backend."
    >
      <DataTable<Violation>
        items={violations.data?.items ?? []}
        emptyLabel="No violations returned by the backend."
        columns={[
          { header: "Type", render: (violation) => violation.violation_type },
          { header: "Evidence", render: (violation) => violation.evidence_uri ?? "No evidence URI" },
          { header: "Occurred", render: (violation) => new Date(violation.occurred_at).toLocaleString() }
        ]}
      />
    </ResourcePage>
  );
}

export function DevicesPage() {
  const { api, user } = useAuth();
  const devices = useAsync(() => api.devices({ limit: 50 }), [api]);

  if (!canViewDevices(user)) {
    return <UnauthorizedState />;
  }
  return (
    <ResourcePage
      title="Devices"
      eyebrow="Infrastructure"
      loading={devices.isLoading}
      error={devices.error}
      empty={!devices.data || devices.data.items.length === 0}
      emptyTitle="No devices returned by the backend."
    >
      <DataTable<DeviceHealth>
        items={devices.data?.items ?? []}
        emptyLabel="No devices returned by the backend."
        columns={[
          { header: "Name", render: (device) => device.name },
          { header: "Identifier", render: (device) => device.identifier },
          { header: "Type", render: (device) => device.type },
          { header: "Status", render: (device) => <StatusBadge label={device.status} tone={device.status === "online" ? "good" : "danger"} /> },
          { header: "Last seen", render: (device) => device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : "Never" }
        ]}
      />
    </ResourcePage>
  );
}

function ResourcePage({
  title,
  eyebrow,
  loading,
  error,
  empty,
  emptyTitle,
  children
}: {
  title: string;
  eyebrow: string;
  loading: boolean;
  error: unknown;
  empty: boolean;
  emptyTitle: string;
  children: React.ReactNode;
}) {
  if (loading) {
    return <LoadingState label={`Loading ${title.toLowerCase()}...`} />;
  }
  if (error) {
    return isUnauthorized(error) ? <UnauthorizedState /> : <ErrorState error={error} />;
  }
  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
      </div>
      {empty ? <EmptyState title={emptyTitle} /> : children}
    </section>
  );
}
