import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { StatusBadge } from "../components/StatusBadge";
import { useRealtime } from "../realtime/RealtimeProvider";

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/intersections", label: "Intersections" },
  { to: "/incidents", label: "Incidents" },
  { to: "/violations", label: "Violations" },
  { to: "/alerts", label: "Alerts" },
  { to: "/devices", label: "Devices" }
];

export function AppShell() {
  const { user, logout } = useAuth();
  const realtime = useRealtime();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>ITMS</strong>
          <span>Operations</span>
        </div>
        <nav aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Traffic Control Center</span>
            <h1>Live Operations Dashboard</h1>
          </div>
          <div className="topbar-actions">
            <StatusBadge
              label={`WebSocket ${realtime.status}`}
              tone={realtime.status === "connected" ? "good" : "warning"}
            />
            <span className="user-chip">
              {user?.display_name} <small>{user?.role}</small>
            </span>
            <button className="button button--secondary" onClick={() => void logout()}>
              Logout
            </button>
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
