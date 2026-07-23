import { useEffect, useMemo, useRef } from "react";
import { useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../../components/AsyncState";
import { useAsync } from "../../../components/useAsync";
import { useAuth } from "../../../auth/AuthProvider";
import { useRealtime } from "../../../realtime/RealtimeProvider";
import { DigitalTwinStatusPanel } from "../components/DigitalTwinStatusPanel";
import { IntersectionScene } from "../components/IntersectionScene";
import { shouldRefreshDigitalTwin } from "../model/applyRealtimeEvent";
import { normalizeDigitalTwinState } from "../model/normalizeDigitalTwinState";

export function DigitalTwinPage() {
  const { id } = useParams();
  const { api } = useAuth();
  const realtime = useRealtime();
  const seenEventIds = useRef(new Set<string>());
  const live = useAsync(() => api.intersectionLive(id ?? ""), [api, id]);
  const reloadLive = live.reload;

  useEffect(() => {
    seenEventIds.current.clear();
  }, [id]);

  useEffect(() => {
    if (!id) {
      return;
    }
    const decision = shouldRefreshDigitalTwin(realtime.lastEvent, id, seenEventIds.current);
    if (decision.shouldRefresh) {
      reloadLive();
    }
  }, [id, realtime.lastEvent, reloadLive]);

  const model = useMemo(
    () =>
      normalizeDigitalTwinState({
        liveState: live.data,
        apiStatus: live.error ? "error" : live.isLoading ? "loading" : live.data ? "ok" : "no-data",
        websocketStatus: realtime.status
      }),
    [live.data, live.error, live.isLoading, realtime.status]
  );
  const sceneDiagnostics = useMemo(
    () => ({
      intersectionId: id ?? model.intersectionId,
      apiStatus: model.apiStatus,
      normalizedLaneCount: Object.values(model.directions).filter((direction) => direction.laneId).length,
      signalStateCount: live.data?.current_signal_states.length ?? 0,
      vehicleVisualCount: Object.values(model.directions).reduce(
        (total, direction) => total + direction.visualVehicleCount,
        0
      )
    }),
    [id, live.data?.current_signal_states.length, model]
  );

  if (!id) {
    return <ErrorState error={new Error("Intersection ID is missing.")} />;
  }

  if (live.isLoading && !live.data) {
    return <LoadingState label="Loading digital twin..." />;
  }

  return (
    <div className="page-grid page-grid--digital-twin">
      <section className="page-header page-header--compact">
        <div>
          <span className="eyebrow">Digital Twin</span>
          <h2>{model.intersectionName}</h2>
          <p>Illustrative four-way intersection view driven by backend live state.</p>
        </div>
      </section>

      {live.error ? <ErrorState error={live.error} /> : null}
      {!live.error && !live.isLoading && !live.data ? (
        <EmptyState
          title="No live state returned for this intersection."
          detail="The 3D view will remain unknown until the backend returns lane, signal and traffic data."
        />
      ) : null}

      <section className="digital-twin-layout digital-twin-layout--pi-desktop">
        <IntersectionScene model={model} diagnostics={sceneDiagnostics} />
        <DigitalTwinStatusPanel model={model} backTo={`/intersections/${id}`} />
      </section>
    </div>
  );
}
