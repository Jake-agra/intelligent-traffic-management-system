import type {
  Alert,
  DashboardSummary,
  DeviceHealth,
  HealthResponse,
  Incident,
  IntersectionDetail,
  IntersectionLiveState,
  IntersectionSummary,
  OperatingMode,
  PaginatedResponse,
  SignalColor,
  SignalModeResponse,
  SignalOverrideResponse,
  TokenPair,
  UserProfile,
  Violation
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface TokenStore {
  getAccessToken(): string | null;
  getRefreshToken(): string | null;
  setTokens(accessToken: string, refreshToken: string): void;
  clear(): void;
}

export class ApiClient {
  constructor(
    private readonly tokenStore: TokenStore,
    private readonly baseUrl = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
  ) {}

  login(email: string, password: string): Promise<TokenPair> {
    return this.request<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false
    });
  }

  async refresh(): Promise<TokenPair> {
    const refreshToken = this.tokenStore.getRefreshToken();
    if (!refreshToken) {
      throw new ApiError("No refresh token is available.", 401);
    }
    return this.request<TokenPair>("/api/v1/auth/refresh", {
      method: "POST",
      body: { refresh_token: refreshToken },
      auth: false,
      retry: false
    });
  }

  logout(): Promise<{ revoked: boolean }> {
    return this.request("/api/v1/auth/logout", {
      method: "POST",
      body: { refresh_token: this.tokenStore.getRefreshToken() ?? "" },
      auth: false,
      retry: false
    });
  }

  me(): Promise<UserProfile> {
    return this.request("/api/v1/auth/me");
  }

  health(): Promise<HealthResponse> {
    return this.request("/api/health", { auth: false });
  }

  dashboardSummary(): Promise<DashboardSummary> {
    return this.request("/api/v1/dashboard/summary");
  }

  intersections(): Promise<IntersectionSummary[]> {
    return this.request("/api/v1/intersections");
  }

  intersection(id: string): Promise<IntersectionDetail> {
    return this.request(`/api/v1/intersections/${id}`);
  }

  intersectionLive(id: string): Promise<IntersectionLiveState> {
    return this.request(`/api/v1/intersections/${id}/live`);
  }

  alerts(params: ResourceParams = {}): Promise<PaginatedResponse<Alert>> {
    return this.request(`/api/v1/alerts${query(params)}`);
  }

  incidents(params: ResourceParams = {}): Promise<PaginatedResponse<Incident>> {
    return this.request(`/api/v1/incidents${query(params)}`);
  }

  violations(params: ResourceParams = {}): Promise<PaginatedResponse<Violation>> {
    return this.request(`/api/v1/violations${query(params)}`);
  }

  devices(params: ResourceParams = {}): Promise<PaginatedResponse<DeviceHealth>> {
    return this.request(`/api/v1/devices${query(params)}`);
  }

  setSignalMode(
    intersectionId: string,
    mode: OperatingMode,
    reason: string
  ): Promise<SignalModeResponse> {
    return this.request(`/api/v1/intersections/${intersectionId}/signal-mode`, {
      method: "POST",
      body: { mode, reason }
    });
  }

  overrideSignal(
    intersectionId: string,
    payload: {
      lane_id: string;
      requested_color: SignalColor;
      duration_seconds: number;
      reason: string;
    }
  ): Promise<SignalOverrideResponse> {
    return this.request(`/api/v1/intersections/${intersectionId}/signal-override`, {
      method: "POST",
      body: payload
    });
  }

  private async request<T>(
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    try {
      return await this.performRequest<T>(path, options);
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status === 401 &&
        options.auth !== false &&
        options.retry !== false &&
        this.tokenStore.getRefreshToken()
      ) {
        try {
          const tokens = await this.refresh();
          this.tokenStore.setTokens(tokens.access_token, tokens.refresh_token);
          return await this.performRequest<T>(path, { ...options, retry: false });
        } catch {
          this.tokenStore.clear();
        }
      }
      throw error;
    }
  }

  private async performRequest<T>(
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    const accessToken = this.tokenStore.getAccessToken();
    if (options.auth !== false && accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: options.method ?? "GET",
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal
      });
      const body = await parseJson(response);
      if (!response.ok) {
        throw new ApiError(errorMessage(body, response.status), response.status, body);
      }
      return body as T;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError("Request timed out.", 0);
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }
}

interface RequestOptions {
  method?: string;
  headers?: HeadersInit;
  body?: unknown;
  auth?: boolean;
  retry?: boolean;
}

interface ResourceParams {
  intersection_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return {};
  }
  return JSON.parse(text) as unknown;
}

function errorMessage(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    return typeof detail === "string" ? detail : `Request failed with status ${status}.`;
  }
  return `Request failed with status ${status}.`;
}

function query(params: ResourceParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
