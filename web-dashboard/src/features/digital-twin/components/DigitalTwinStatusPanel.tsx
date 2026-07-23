import { Link } from "react-router-dom";
import { StatusBadge } from "../../../components/StatusBadge";
import type { DigitalTwinViewModel, DirectionTwinState, TwinSignal } from "../types";
import { DIRECTIONS } from "../types";

const signalTones: Record<TwinSignal, "neutral" | "good" | "warning" | "danger"> = {
  red: "danger",
  yellow: "warning",
  green: "good",
  unknown: "neutral"
};

export function DigitalTwinStatusPanel({
  model,
  backTo
}: {
  model: DigitalTwinViewModel;
  backTo: string;
}) {
  return (
    <aside className="digital-twin-status" aria-label="Digital twin textual state">
      <div className="panel">
        <div className="panel-heading-row">
          <h3>{model.intersectionName}</h3>
          <Link className="button button--secondary" to={backTo}>
            Back to detail
          </Link>
        </div>
        <dl className="status-list">
          <div>
            <dt>API</dt>
            <dd><StatusBadge label={model.apiStatus} tone={model.apiStatus === "ok" ? "good" : "warning"} /></dd>
          </div>
          <div>
            <dt>WebSocket</dt>
            <dd><StatusBadge label={model.websocketStatus} tone={model.websocketStatus === "connected" ? "good" : "warning"} /></dd>
          </div>
          <div>
            <dt>Last update</dt>
            <dd>{model.lastUpdateAt ? new Date(model.lastUpdateAt).toLocaleTimeString() : "No update"}</dd>
          </div>
          <div>
            <dt>Stale data</dt>
            <dd>{model.isStale ? "Yes" : "No"}</dd>
          </div>
        </dl>
        {model.staleReason ? (
          <div className="state-panel state-panel--warning">{model.staleReason}</div>
        ) : null}
      </div>

      <div className="panel">
        <h3>Signals and density</h3>
        <div className="direction-state-grid">
          {DIRECTIONS.map((direction) => (
            <DirectionState key={direction} state={model.directions[direction]} />
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>Legend</h3>
        <div className="legend-list">
          {(["red", "yellow", "green", "unknown"] as const).map((signal) => (
            <span key={signal} className="legend-item">
              <span className={`legend-dot legend-dot--${signal}`} aria-hidden="true" />
              {signal}
            </span>
          ))}
        </div>
      </div>
    </aside>
  );
}

function DirectionState({ state }: { state: DirectionTwinState }) {
  return (
    <section className="direction-state-card">
      <div className="direction-state-card__header">
        <strong>{state.direction}</strong>
        <StatusBadge label={state.signal} tone={signalTones[state.signal]} />
      </div>
      <dl className="compact-list">
        <div>
          <dt>Lane</dt>
          <dd>{state.laneName}</dd>
        </div>
        <div>
          <dt>Density</dt>
          <dd>{state.lastTrafficAt ? state.density : "No traffic data"}</dd>
        </div>
        <div>
          <dt>Vehicles</dt>
          <dd>{state.vehicleCount ?? 0}</dd>
        </div>
        <div>
          <dt>Visible vehicles</dt>
          <dd>{state.visualVehicleCount}</dd>
        </div>
        <div>
          <dt>Mapping</dt>
          <dd>{state.mappingStatus}</dd>
        </div>
      </dl>
    </section>
  );
}
