import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";
import { ApiClient, ApiError } from "../api/client";
import type { UserProfile } from "../api/types";
import { sessionTokenStore } from "./session";

interface AuthContextValue {
  api: ApiClient;
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
  reloadUser(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const api = useMemo(() => new ApiClient(sessionTokenStore), []);

  const reloadUser = useCallback(async () => {
    if (!sessionTokenStore.getAccessToken()) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      setUser(await api.me());
      setError(null);
    } catch (requestError) {
      sessionTokenStore.clear();
      setUser(null);
      setError(messageFor(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void reloadUser();
  }, [reloadUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.login(email, password);
      sessionTokenStore.setTokens(response.access_token, response.refresh_token);
      setUser(response.user);
      setError(null);
    },
    [api]
  );

  const logout = useCallback(async () => {
    try {
      if (sessionTokenStore.getRefreshToken()) {
        await api.logout();
      }
    } finally {
      sessionTokenStore.clear();
      setUser(null);
    }
  }, [api]);

  const value = useMemo(
    () => ({
      api,
      user,
      isAuthenticated: user !== null,
      isLoading,
      error,
      login,
      logout,
      reloadUser
    }),
    [api, error, isLoading, login, logout, reloadUser, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return value;
}

export function canControlSignals(user: UserProfile | null): boolean {
  return user?.role === "admin";
}

export function canViewIncidents(user: UserProfile | null): boolean {
  return user?.role === "admin" || user?.role === "emergency_responder";
}

export function canViewViolations(user: UserProfile | null): boolean {
  return user?.role === "admin" || user?.role === "police";
}

export function canViewDevices(user: UserProfile | null): boolean {
  return user?.role === "admin";
}

export function canViewDashboard(user: UserProfile | null): boolean {
  return user?.role === "admin" || user?.role === "analyst";
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed.";
}
