import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { DigitalTwinPage } from "./features/digital-twin/pages/DigitalTwinPage";
import { AppShell } from "./layouts/AppShell";
import { RealtimeProvider } from "./realtime/RealtimeProvider";
import { IntersectionDetailPage } from "./pages/IntersectionDetailPage";
import { IntersectionsPage } from "./pages/IntersectionsPage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { AlertsPage, DevicesPage, IncidentsPage, ViolationsPage } from "./pages/ResourcePages";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route
              element={
                <RealtimeProvider>
                  <AppShell />
                </RealtimeProvider>
              }
            >
              <Route index element={<OverviewPage />} />
              <Route path="intersections" element={<IntersectionsPage />} />
              <Route path="intersections/:id" element={<IntersectionDetailPage />} />
              <Route path="intersections/:id/digital-twin" element={<DigitalTwinPage />} />
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="violations" element={<ViolationsPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="devices" element={<DevicesPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
