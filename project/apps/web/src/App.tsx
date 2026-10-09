import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { OverviewPage } from "./pages/OverviewPage";
import { RequirementsPage } from "./pages/RequirmentsPage";
import { RequirementDetailsPage } from "./pages/RequirmentDetailsPage";
import { ReportsAnalyticsPage } from "./pages/ReportAnalyticsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/quality/overview" replace />} />

          <Route path="/quality/overview" element={<OverviewPage />} />

          <Route path="/quality/requirements" element={<RequirementsPage />} />

          <Route
            path="/quality/requirements/:requirementId"
            element={<RequirementDetailsPage />}
          />

          <Route path="/quality/reports" element={<ReportsAnalyticsPage />} />

          <Route
            path="*"
            element={<Navigate to="/quality/overview" replace />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
