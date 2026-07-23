import { ApiError } from "../api/client";

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return <div className="state-panel">{label}</div>;
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="state-panel">
      <strong>{title}</strong>
      {detail ? <p>{detail}</p> : null}
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Request failed.";
  return <div className="state-panel state-panel--error">{message}</div>;
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export function UnauthorizedState() {
  return (
    <div className="state-panel state-panel--warning">
      You are signed in, but this role cannot view this resource.
    </div>
  );
}
