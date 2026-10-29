import { lazy, Suspense } from "react";

import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import DashboardLayout from "../Layouts/DashboardLayout";
import QualityLayout from "../Layouts/QualityLayout.jsx";
import DashboardOverview from "../pages/DashboardOverview";

const QualityApp = lazy(() => import("../component/quality/QualityApp.jsx"));

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<DashboardOverview />} />
          <Route path="quality/*" element={
            <QualityLayout>
              <Suspense fallback={<p role="status">Loading quality intelligence...</p>}>
                <QualityApp />
              </Suspense>
            </QualityLayout>
          } />

        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default AppRoutes;
