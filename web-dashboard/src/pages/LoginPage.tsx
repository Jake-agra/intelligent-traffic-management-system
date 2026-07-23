import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (auth.isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await auth.login(email, password);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";
      navigate(from, { replace: true });
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="login-panel">
        <span className="eyebrow">Intelligent Traffic Management System</span>
        <h1>Operator Sign In</h1>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Email
            <input
              autoComplete="email"
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              autoComplete="current-password"
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? <div className="form-error">{error}</div> : null}
          <button className="button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
