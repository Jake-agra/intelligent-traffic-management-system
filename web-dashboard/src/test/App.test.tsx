import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

const user = {
  id: "user-1",
  email: "operator@example.com",
  display_name: "Operator One",
  role: "admin",
  is_active: true,
  created_at: "2026-07-22T00:00:00Z",
  updated_at: "2026-07-22T00:00:00Z"
};

const analyst = { ...user, role: "analyst", email: "analyst@example.com" };
const intersectionId = "00000000-0000-0000-0000-000000000002";
const laneId = "00000000-0000-0000-0000-000000000101";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  onopen: (() => void) | null = null;
  onmessage: ((message: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];

  constructor(public readonly url: string) {
    MockWebSocket.instances.push(this);
    window.setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.();
      this.emit({
        type: "connection.acknowledged",
        connection_id: "connection-1",
        supported_events: ["signal.updated"]
      });
    }, 0);
  }

  send(value: string) {
    this.sent.push(value);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  emit(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent);
  }
}

beforeEach(() => {
  window.sessionStorage.clear();
  window.history.pushState({}, "", "/");
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.stubGlobal("confirm", vi.fn(() => true));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("dashboard app", () => {
  it("handles login success", async () => {
    mockFetch();
    window.history.pushState({}, "", "/login");
    render(<App />);

    await userEvent.type(screen.getByLabelText(/email/i), "operator@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "correct-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/network status/i, {}, { timeout: 15000 })).toBeInTheDocument();
    expect(window.sessionStorage.getItem("itms.access_token")).toBe("access-token");
  });

  it("handles login failure", async () => {
    mockFetch({
      "POST /api/v1/auth/login": jsonResponse({ detail: "Invalid credentials." }, 401)
    });
    window.history.pushState({}, "", "/login");
    render(<App />);

    await userEvent.type(screen.getByLabelText(/email/i), "operator@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
  });

  it("protects authenticated routes", async () => {
    mockFetch();
    render(<App />);

    expect(await screen.findByRole("heading", { name: /operator sign in/i })).toBeInTheDocument();
  });

  it("loads the current user", async () => {
    window.sessionStorage.setItem("itms.access_token", "access-token");
    window.sessionStorage.setItem("itms.refresh_token", "refresh-token");
    mockFetch();

    render(<App />);

    expect(await screen.findByText("Operator One")).toBeInTheDocument();
  });

  it("renders the dashboard summary", async () => {
    authenticated();
    mockFetch();

    render(<App />);

    expect(await screen.findByText("Total intersections")).toBeInTheDocument();
    expect(screen.getByText("Active incidents")).toBeInTheDocument();
    expect(screen.getByText("Online devices")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    authenticated();
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    render(<App />);

    expect(screen.getByText(/loading current user/i)).toBeInTheDocument();
  });

  it("shows empty state", async () => {
    authenticated();
    mockFetch({ "GET /api/v1/intersections": jsonResponse([]) });
    window.history.pushState({}, "", "/intersections");

    render(<App />);

    expect(await screen.findByText(/no intersections configured/i)).toBeInTheDocument();
  });

  it("shows API error state", async () => {
    authenticated();
    mockFetch({ "GET /api/v1/dashboard/summary": jsonResponse({ detail: "Backend unavailable." }, 500) });

    render(<App />);

    expect(await screen.findByText(/backend unavailable/i)).toBeInTheDocument();
  });

  it("renders intersection list", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", "/intersections");

    render(<App />);

    expect(await screen.findByText("Central Junction")).toBeInTheDocument();
  });

  it("renders intersection detail", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}`);

    render(<App />);

    expect((await screen.findAllByText("Northbound")).length).toBeGreaterThan(0);
    expect(screen.getByText("Current signal states")).toBeInTheDocument();
  });

  it("shows WebSocket connection status", async () => {
    authenticated();
    mockFetch();

    render(<App />);

    expect(await screen.findByText(/WebSocket connected/i)).toBeInTheDocument();
  });

  it("updates visible state after a WebSocket event", async () => {
    authenticated();
    let liveColor = "red";
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: () => jsonResponse(liveState(liveColor))
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}`);
    render(<App />);

    await waitFor(() => expect(hasSignalBadge("red")).toBe(true));
    liveColor = "green";
    act(() => {
      MockWebSocket.instances[0].emit({
        event: "signal.updated",
        version: 1,
        event_id: "event-1",
        occurred_at: "2026-07-22T00:00:00Z",
        intersection_id: intersectionId,
        data: { color: "green" }
      });
    });

    await waitFor(() => expect(hasSignalBadge("green")).toBe(true));
  });

  it("reconnects after socket close", async () => {
    authenticated();
    mockFetch();
    render(<App />);

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    act(() => {
      MockWebSocket.instances[0].close();
    });

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(2), { timeout: 2000 });
  });

  it("hides signal controls from unauthorized roles", async () => {
    authenticated();
    mockFetch({ "GET /api/v1/auth/me": jsonResponse(analyst) });
    window.history.pushState({}, "", `/intersections/${intersectionId}`);

    render(<App />);

    await screen.findAllByText("Northbound");
    expect(screen.queryByLabelText(/signal controls/i)).not.toBeInTheDocument();
  });

  it("shows signal controls for admins", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}`);

    render(<App />);

    expect(await screen.findByLabelText(/signal controls/i)).toBeInTheDocument();
  });

  it("requires manual override confirmation", async () => {
    authenticated();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}`);
    render(<App />);

    const controls = await screen.findByLabelText(/signal controls/i);
    await userEvent.type(within(controls).getAllByLabelText(/reason/i)[1], "Test override");
    await userEvent.click(within(controls).getByRole("button", { name: /send override/i }));

    expect(confirm).toHaveBeenCalled();
  });

  it("submits a successful signal-control request", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}`);
    render(<App />);

    const controls = await screen.findByLabelText(/signal controls/i);
    await userEvent.type(within(controls).getAllByLabelText(/reason/i)[1], "Clear traffic");
    await userEvent.click(within(controls).getByRole("button", { name: /send override/i }));

    expect(await screen.findByText(/operation id/i)).toBeInTheDocument();
  });

  it("shows failed signal-control request", async () => {
    authenticated();
    mockFetch({
      [`POST /api/v1/intersections/${intersectionId}/signal-override`]: jsonResponse(
        { detail: "Signal override duration exceeds configured maximum." },
        409
      )
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}`);
    render(<App />);

    const controls = await screen.findByLabelText(/signal controls/i);
    await userEvent.type(within(controls).getAllByLabelText(/reason/i)[1], "Too long");
    await userEvent.click(within(controls).getByRole("button", { name: /send override/i }));

    expect(await screen.findByText(/duration exceeds/i)).toBeInTheDocument();
  });
});

function authenticated() {
  window.sessionStorage.setItem("itms.access_token", "access-token");
  window.sessionStorage.setItem("itms.refresh_token", "refresh-token");
}

function mockFetch(overrides: Record<string, ResponseFactory | Response> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const key = `${init?.method ?? "GET"} ${url.pathname}`;
      const override = overrides[key];
      if (override) {
        return Promise.resolve(typeof override === "function" ? override() : override);
      }
      return Promise.resolve(defaultResponse(key));
    })
  );
}

type ResponseFactory = () => Response;

function defaultResponse(key: string): Response {
  const responses: Record<string, Response> = {
    "POST /api/v1/auth/login": jsonResponse({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
      expires_in: 900,
      user
    }),
    "GET /api/v1/auth/me": jsonResponse(user),
    "POST /api/v1/auth/logout": jsonResponse({ revoked: true }),
    "GET /api/health": jsonResponse({
      service_name: "ITMS",
      api_version: "0.1.0",
      environment: "test",
      api_status: "ok",
      database_status: "ok"
    }),
    "GET /api/v1/dashboard/summary": jsonResponse({
      generated_at: "2026-07-22T00:00:00Z",
      intersections: { total: 1, active: 1 },
      traffic: { total_readings: 1, latest_reading_at: "2026-07-22T00:00:00Z" },
      signals: { current_states: 1 },
      incidents: { active: 1, total: 1 },
      violations: { recent: 1, total: 1 },
      alerts: { active: 1, total: 1 },
      devices: { total: 1, online: 1, offline: 0, degraded: 0 }
    }),
    "GET /api/v1/intersections": jsonResponse([intersection()]),
    [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(liveState("green")),
    "GET /api/v1/alerts": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/v1/incidents": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/v1/violations": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/v1/devices": jsonResponse({
      items: [
        {
          id: "device-1",
          intersection_id: intersectionId,
          lane_id: laneId,
          identifier: "pi-1",
          name: "Pi Controller",
          type: "raspberry_pi",
          status: "online",
          last_seen_at: "2026-07-22T00:00:00Z"
        }
      ],
      total: 1,
      limit: 50,
      offset: 0
    }),
    [`POST /api/v1/intersections/${intersectionId}/signal-override`]: jsonResponse({
      action: "signal.override",
      audit_log_id: "audit-1",
      emitted_event: "signal.updated",
      intersection_id: intersectionId,
      lane_id: laneId,
      color: "green",
      duration_seconds: 5,
      started_at: "2026-07-22T00:00:00Z",
      ends_at: "2026-07-22T00:00:05Z",
      signal_event_id: "signal-event-1"
    }),
    [`POST /api/v1/intersections/${intersectionId}/signal-mode`]: jsonResponse({
      action: "signal.mode_change",
      audit_log_id: "audit-2",
      emitted_event: "signal.updated",
      intersection_id: intersectionId,
      mode: "manual",
      reason: "Manual operation"
    })
  };
  return responses[key] ?? jsonResponse({ detail: `Unhandled ${key}` }, 404);
}

function intersection() {
  return {
    id: intersectionId,
    name: "Central Junction",
    location_description: "Main road",
    latitude: null,
    longitude: null,
    is_active: true,
    created_at: "2026-07-22T00:00:00Z",
    updated_at: "2026-07-22T00:00:00Z"
  };
}

function liveState(color: string) {
  return {
    intersection: intersection(),
    lanes: [
      {
        id: laneId,
        intersection_id: intersectionId,
        name: "Northbound",
        direction: "north",
        sequence: 1,
        is_active: true,
        created_at: "2026-07-22T00:00:00Z",
        updated_at: "2026-07-22T00:00:00Z"
      }
    ],
    latest_traffic_readings: [],
    current_signal_states: [
      {
        id: "signal-1",
        intersection_id: intersectionId,
        lane_id: laneId,
        color,
        operating_mode: "manual",
        started_at: "2026-07-22T00:00:00Z",
        ends_at: null
      }
    ],
    active_incidents: [],
    recent_violations: [],
    active_alerts: [],
    devices: [],
    generated_at: "2026-07-22T00:00:00Z"
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function hasSignalBadge(label: string): boolean {
  return screen
    .getAllByText(label)
    .some((element) => element.classList.contains("status-badge"));
}
