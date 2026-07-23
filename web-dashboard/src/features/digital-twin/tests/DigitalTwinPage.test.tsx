import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../../App";

const user = {
  id: "user-1",
  email: "operator@example.com",
  display_name: "Operator One",
  role: "admin",
  is_active: true,
  created_at: "2026-07-22T00:00:00Z",
  updated_at: "2026-07-22T00:00:00Z"
};

const intersectionId = "00000000-0000-0000-0000-000000000002";

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
        supported_events: ["signal.updated", "traffic.updated"]
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
  (globalThis as { __ITMS_FAIL_CANVAS?: boolean }).__ITMS_FAIL_CANVAS = false;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  (globalThis as { __ITMS_FAIL_CANVAS?: boolean }).__ITMS_FAIL_CANVAS = false;
});

describe("digital twin page", () => {
  it("protects the route", async () => {
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByRole("heading", { name: /operator sign in/i })).toBeInTheDocument();
  });

  it("loads intersection live data into the textual fallback and 3D shell", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(
      await screen.findByText(/illustrative four-way intersection/i, {}, { timeout: 5000 })
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /central junction/i })).toHaveLength(2);
    expect(screen.getByTestId("digital-twin-scene-canvas")).toBeInTheDocument();
    expect(screen.getByLabelText(/scene direction labels/i)).toHaveTextContent("NORTH");
    expect(screen.getByLabelText(/scene direction labels/i)).toHaveTextContent("SOUTH");
    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("API load statusok");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("Northbound");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("green");
  });

  it("renders the basic scene when live API data is empty", async () => {
    authenticated();
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse({
        ...liveState(),
        lanes: [],
        latest_traffic_readings: [],
        current_signal_states: []
      })
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByTestId("digital-twin-scene-canvas")).toBeInTheDocument();
    expect(screen.getByLabelText(/scene direction labels/i)).toHaveTextContent("NORTH");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("unknown");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("No traffic data");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("Visible vehicles0");
    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("Normalized lanes0");
    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("Signal states0");
    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("Vehicle visuals0");
  });

  it("renders unknown signal states without hiding the scene", async () => {
    authenticated();
    const state = liveState();
    state.current_signal_states = [signal("lane-north", "flashing-blue")];
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(state)
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByTestId("digital-twin-scene-canvas")).toBeInTheDocument();
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("unknown");
    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("Signal states1");
  });

  it("keeps the explicit visible scene viewport class", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByTestId("digital-twin-scene-viewport")).toHaveClass(
      "digital-twin-scene-viewport"
    );
    expect(screen.getByTestId("digital-twin-scene-canvas")).toHaveClass("digital-twin-canvas");
    expect(screen.getByTestId("digital-twin-scene-viewport").closest(".digital-twin-layout")).toHaveClass(
      "digital-twin-layout--pi-desktop"
    );
  });

  it("uses the Raspberry Pi desktop layout without horizontal overflow classes", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    await screen.findByTestId("digital-twin-scene-canvas");
    expect(document.querySelector(".page-grid--digital-twin")).toBeInTheDocument();
    expect(document.querySelector(".page-header--compact")).toBeInTheDocument();
    expect(document.querySelector(".digital-twin-layout--pi-desktop")).toBeInTheDocument();
  });

  it("shows loading state while live data is pending", async () => {
    authenticated();
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: () => new Promise<Response>(() => undefined)
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByText(/loading digital twin/i)).toBeInTheDocument();
  });

  it("shows API error state", async () => {
    authenticated();
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(
        { detail: "Intersection not found." },
        404
      )
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByText(/intersection not found/i)).toBeInTheDocument();
  });

  it("shows a clear API error for an invalid intersection ID", async () => {
    authenticated();
    mockFetch({
      "GET /api/v1/intersections/not-a-uuid/live": jsonResponse(
        { detail: "Invalid intersection ID." },
        422
      )
    });
    window.history.pushState({}, "", "/intersections/not-a-uuid/digital-twin");

    render(<App />);

    expect(await screen.findByText(/invalid intersection id/i)).toBeInTheDocument();
  });

  it("shows no-data state", async () => {
    authenticated();
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(null)
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByText(/no live state returned/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("unknown");
  });

  it("refreshes signal state after a WebSocket signal update", async () => {
    authenticated();
    let color: "red" | "green" = "red";
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: () => jsonResponse(liveState({ northSignal: color }))
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);
    render(<App />);

    await waitFor(() => expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("red"));
    color = "green";
    act(() => {
      MockWebSocket.instances[0].emit(realtimeEvent("signal.updated", "signal-event-1"));
    });

    await waitFor(() => expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("green"));
  });

  it("refreshes traffic density after a WebSocket traffic update", async () => {
    authenticated();
    let vehicles = 2;
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: () =>
        jsonResponse(liveState({ northVehicles: vehicles, northDensity: vehicles > 5 ? "high" : "low" }))
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);
    render(<App />);

    await waitFor(() => expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("low"));
    vehicles = 9;
    act(() => {
      MockWebSocket.instances[0].emit(realtimeEvent("traffic.updated", "traffic-event-1"));
    });

    await waitFor(() => expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("high"));
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("9");
  });

  it("shows seeded traffic counts consistently in text and scene diagnostics", async () => {
    authenticated();
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(
        liveState({ northVehicles: 7, northDensity: "medium" })
      )
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByTestId("digital-twin-scene-canvas")).toBeInTheDocument();
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("medium");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("Vehicles7");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("Visible vehicles7");
  });

  it("keeps textual fallback when WebGL initialization fails", async () => {
    authenticated();
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    (globalThis as { __ITMS_FAIL_CANVAS?: boolean }).__ITMS_FAIL_CANVAS = true;
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findAllByText(/scene initialization was forced to fail/i)).toHaveLength(1);
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("Northbound");
  });

  it("reset camera restores the overview preset", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);
    render(<App />);

    await screen.findByTestId("digital-twin-scene-canvas");
    await userEvent.click(screen.getByRole("button", { name: "North" }));
    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("Camera presetnorth");

    await userEvent.click(screen.getByRole("button", { name: /reset camera/i }));

    expect(screen.getByLabelText(/digital twin diagnostics/i)).toHaveTextContent("Camera presetoverview");
  });

  it("missing lanes do not suppress the basic intersection geometry", async () => {
    authenticated();
    const state = liveState();
    state.lanes = state.lanes.filter((lane) => lane.direction === "north");
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(state)
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}/digital-twin`);

    render(<App />);

    expect(await screen.findByTestId("digital-twin-scene-canvas")).toBeInTheDocument();
    expect(screen.getByLabelText(/scene direction labels/i)).toHaveTextContent("EAST");
    expect(screen.getByLabelText(/digital twin textual state/i)).toHaveTextContent("missing-lane");
  });

  it("links to the digital twin from intersection detail", async () => {
    authenticated();
    mockFetch();
    window.history.pushState({}, "", `/intersections/${intersectionId}`);
    render(<App />);

    const link = await screen.findByRole("link", { name: /digital twin/i });
    await userEvent.click(link);

    expect(await screen.findByText(/illustrative four-way intersection/i)).toBeInTheDocument();
  });

  it("shows one latest signal state per direction on intersection detail", async () => {
    authenticated();
    const state = liveState();
    state.current_signal_states = [
      signal("lane-north", "red", "2026-07-22T00:00:01Z", "signal-north-old"),
      signal("lane-north", "green", "2026-07-22T00:00:02Z", "signal-north-new"),
      signal("lane-south", "red", "2026-07-22T00:00:02Z", "signal-south-a"),
      signal("lane-south", "yellow", "2026-07-22T00:00:02Z", "signal-south-b"),
      signal("lane-east", "red", "2026-07-22T00:00:02Z", "signal-east"),
      signal("lane-west", "red", "2026-07-22T00:00:02Z", "signal-west")
    ];
    mockFetch({
      [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(state)
    });
    window.history.pushState({}, "", `/intersections/${intersectionId}`);

    render(<App />);

    const signalPanel = (await screen.findByRole("heading", { name: /current signal states/i })).closest(
      ".panel"
    );
    expect(signalPanel).not.toBeNull();
    expect(screen.getByText("Signals").parentElement).toHaveTextContent("4");
    expect(within(signalPanel as HTMLElement).getAllByText("Northbound")).toHaveLength(1);
    expect(within(signalPanel as HTMLElement).getAllByText("Southbound")).toHaveLength(1);
    expect(signalPanel).toHaveTextContent("green");
    expect(signalPanel).toHaveTextContent("yellow");
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

type ResponseFactory = () => Response | Promise<Response>;

function defaultResponse(key: string): Response {
  const responses: Record<string, Response> = {
    "GET /api/v1/auth/me": jsonResponse(user),
    [`GET /api/v1/intersections/${intersectionId}/live`]: jsonResponse(liveState()),
    "GET /api/v1/alerts": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/v1/incidents": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/v1/violations": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/v1/devices": jsonResponse({ items: [], total: 0, limit: 50, offset: 0 }),
    "GET /api/health": jsonResponse({
      service_name: "ITMS",
      api_version: "0.1.0",
      environment: "test",
      api_status: "ok",
      database_status: "ok"
    })
  };
  return responses[key] ?? jsonResponse({ detail: `Unhandled ${key}` }, 404);
}

function liveState({
  northSignal = "green",
  northVehicles = 4,
  northDensity = "medium"
}: {
  northSignal?: "red" | "green";
  northVehicles?: number;
  northDensity?: "low" | "medium" | "high";
} = {}) {
  return {
    intersection: {
      id: intersectionId,
      name: "Central Junction",
      location_description: "Main road",
      latitude: null,
      longitude: null,
      is_active: true,
      created_at: "2026-07-22T00:00:00Z",
      updated_at: "2026-07-22T00:00:00Z"
    },
    lanes: [
      lane("lane-north", "Northbound", "north", 1),
      lane("lane-south", "Southbound", "south", 2),
      lane("lane-east", "Eastbound", "east", 3),
      lane("lane-west", "Westbound", "west", 4)
    ],
    latest_traffic_readings: [
      traffic("lane-north", northVehicles, northDensity),
      traffic("lane-south", 1, "low"),
      traffic("lane-east", 6, "medium"),
      traffic("lane-west", 8, "high")
    ],
    current_signal_states: [
      signal("lane-north", northSignal),
      signal("lane-south", northSignal),
      signal("lane-east", "red"),
      signal("lane-west", "red")
    ],
    active_incidents: [],
    recent_violations: [],
    active_alerts: [],
    devices: [],
    generated_at: "2026-07-22T00:00:00Z"
  };
}

function lane(id: string, name: string, direction: string, sequence: number) {
  return {
    id,
    intersection_id: intersectionId,
    name,
    direction,
    sequence,
    is_active: true,
    created_at: "2026-07-22T00:00:00Z",
    updated_at: "2026-07-22T00:00:00Z"
  };
}

function signal(
  laneId: string,
  color: string,
  startedAt = "2026-07-22T00:00:00Z",
  id = `signal-${laneId}`
) {
  return {
    id,
    intersection_id: intersectionId,
    lane_id: laneId,
    color,
    operating_mode: "manual",
    started_at: startedAt,
    ends_at: null
  };
}

function traffic(laneId: string, vehicleCount: number, density: "low" | "medium" | "high") {
  return {
    id: `traffic-${laneId}`,
    intersection_id: intersectionId,
    lane_id: laneId,
    device_id: null,
    vehicle_count: vehicleCount,
    density,
    captured_at: "2026-07-22T00:00:00Z"
  };
}

function realtimeEvent(event: "signal.updated" | "traffic.updated", eventId: string) {
  return {
    event,
    version: 1,
    event_id: eventId,
    occurred_at: "2026-07-22T00:00:00Z",
    intersection_id: intersectionId,
    data: {}
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
