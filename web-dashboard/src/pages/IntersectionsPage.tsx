import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { useAsync } from "../components/useAsync";
import { useAuth } from "../auth/AuthProvider";

export function IntersectionsPage() {
  const { api } = useAuth();
  const [search, setSearch] = useState("");
  const intersections = useAsync(() => api.intersections(), [api]);
  const filtered = useMemo(
    () =>
      (intersections.data ?? []).filter((item) =>
        `${item.name} ${item.location_description ?? ""}`.toLowerCase().includes(search.toLowerCase())
      ),
    [intersections.data, search]
  );

  if (intersections.isLoading) {
    return <LoadingState label="Loading intersections..." />;
  }
  if (intersections.error) {
    return <ErrorState error={intersections.error} />;
  }
  if (!intersections.data || intersections.data.length === 0) {
    return <EmptyState title="No intersections configured." />;
  }

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <span className="eyebrow">Intersections</span>
          <h2>Managed junctions</h2>
        </div>
        <label className="search-field">
          Search
          <input value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>
      </div>
      <DataTable
        items={filtered}
        emptyLabel="No intersections match the current filter."
        columns={[
          { header: "Name", render: (item) => <Link to={`/intersections/${item.id}`}>{item.name}</Link> },
          { header: "Status", render: (item) => <StatusBadge label={item.is_active ? "active" : "inactive"} tone={item.is_active ? "good" : "neutral"} /> },
          { header: "Location", render: (item) => item.location_description ?? "Unspecified" },
          { header: "Updated", render: (item) => formatDate(item.updated_at) }
        ]}
      />
    </section>
  );
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}
