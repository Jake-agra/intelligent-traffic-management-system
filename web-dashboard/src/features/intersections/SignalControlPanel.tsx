import { FormEvent, useState } from "react";
import type {
  ControllerState,
  Lane,
  OperatingMode,
  SignalColor,
  SignalModeResponse,
  SignalOverrideResponse
} from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";

export function SignalControlPanel({
  intersectionId,
  lanes,
  controllerState,
  onSuccess
}: {
  intersectionId: string;
  lanes: Lane[];
  controllerState: ControllerState | null;
  onSuccess(): void;
}) {
  const { api } = useAuth();
  const [mode, setMode] = useState<OperatingMode>("manual");
  const [laneId, setLaneId] = useState(lanes[0]?.id ?? "");
  const [color, setColor] = useState<SignalColor>("green");
  const [duration, setDuration] = useState(5);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<SignalOverrideResponse | SignalModeResponse | { audit_log_id: string } | null>(null);
  const confirmedMode = controllerState?.mode ?? "manual";
  const modePending = controllerState?.command_status === "pending";
  const manualConfirmed = confirmedMode === "manual" && !modePending;

  async function submitMode(event: FormEvent) {
    event.preventDefault();
    if (!window.confirm("Manual signal mode affects physical hardware. Continue?")) {
      return;
    }
    await submit(async () => api.setSignalMode(intersectionId, mode, reason));
  }

  async function submitOverride(event: FormEvent) {
    event.preventDefault();
    if (!window.confirm("Manual signal overrides affect physical hardware. Continue?")) {
      return;
    }
    await submit(() =>
      api.overrideSignal(intersectionId, {
        lane_id: laneId,
        requested_color: color,
        duration_seconds: duration,
        reason
      })
    );
  }

  async function switchMode(nextMode: OperatingMode, confirmText: string) {
    if (!window.confirm(confirmText)) {
      return;
    }
    await submit(async () => api.setSignalMode(intersectionId, nextMode, reason || `Switch to ${nextMode}`));
  }

  async function submit(request: () => Promise<SignalOverrideResponse | SignalModeResponse | { audit_log_id: string }>) {
    setPending(true);
    setError(null);
    setResponse(null);
    try {
      const result = await request();
      setResponse(result);
      onSuccess();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Signal request failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel control-panel" aria-label="Signal controls">
      <div className="warning-banner">Manual overrides affect physical traffic-light hardware.</div>
      <div className="state-panel">
        Controller mode: <strong>{confirmedMode}</strong>
        {controllerState?.phase ? ` | Phase: ${controllerState.phase}` : ""}
        {modePending ? " | Mode change pending confirmation" : ""}
      </div>
      <div className="control-grid">
        <form onSubmit={(event) => void submitMode(event)}>
          <h3>Signal mode</h3>
          <label>
            Mode
            <select value={mode} onChange={(event) => setMode(event.target.value as OperatingMode)}>
              <option value="manual">manual</option>
              <option value="automatic">automatic</option>
              <option value="failsafe">failsafe</option>
            </select>
          </label>
          <label>
            Reason
            <input required value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
          <button className="button" disabled={pending} type="submit">
            Set mode
          </button>
        </form>

        <div>
          <h3>Controller actions</h3>
          <div className="button-row">
            <button
              className="button"
              disabled={pending || modePending || confirmedMode === "manual"}
              type="button"
              onClick={() => void switchMode("manual", "Switch to manual mode and pause automatic control?")}
            >
              Switch to manual
            </button>
            <button
              className="button button--secondary"
              disabled={pending || modePending || confirmedMode === "automatic"}
              type="button"
              onClick={() => void switchMode("automatic", "Resume automatic fixed-time control from all red?")}
            >
              Resume automatic
            </button>
            <button
              className="button button--danger"
              disabled={pending}
              type="button"
              onClick={() => void switchMode("manual", "Emergency all red will interrupt active control. Continue?")}
            >
              Emergency all red
            </button>
          </div>
        </div>

        {manualConfirmed ? (
          <form onSubmit={(event) => void submitOverride(event)}>
            <h3>Signal override</h3>
            <label>
              Lane
              <select required value={laneId} onChange={(event) => setLaneId(event.target.value)}>
                {lanes.map((lane) => (
                  <option key={lane.id} value={lane.id}>
                    {lane.name} ({lane.direction})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Signal
              <select value={color} onChange={(event) => setColor(event.target.value as SignalColor)}>
                <option value="red">red</option>
                <option value="yellow">yellow</option>
                <option value="green">green</option>
              </select>
            </label>
            <label>
              Duration seconds
              <input
                min={1}
                required
                type="number"
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
              />
            </label>
            <label>
              Reason
              <input required value={reason} onChange={(event) => setReason(event.target.value)} />
            </label>
            <button className="button" disabled={pending || lanes.length === 0} type="submit">
              Send override
            </button>
          </form>
        ) : (
          <div className="state-panel">
            Manual signal controls are available after manual mode is confirmed by the physical controller.
          </div>
        )}
      </div>
      {pending ? <div className="state-panel">Signal request pending...</div> : null}
      {error ? <div className="state-panel state-panel--error">{error}</div> : null}
      {response ? (
        <div className="state-panel state-panel--success">
          Request accepted. Operation ID: {operationId(response)}
        </div>
      ) : null}
    </section>
  );
}

function operationId(response: SignalOverrideResponse | SignalModeResponse | { audit_log_id: string }): string {
  if ("command_id" in response && response.command_id) {
    return response.command_id;
  }
  if ("signal_event_id" in response && response.signal_event_id) {
    return response.signal_event_id;
  }
  return response.audit_log_id;
}
