import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export function ProtectedRoute() {
  const auth = useAuth();
  const location = useLocation();

  if (auth.isLoading) {
    return <main className="auth-screen">Loading current user...</main>;
  }

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
