import React from "react";

import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useParams,
} from "react-router-dom";
import DashboardLayout from "../Layouts/DashboardLayout";
import DashboardOverview from "../pages/DashboardOverview";
import RequirementIntelligencePage from "../modules/requirement-intelligence/RequirementIntelligencePage";

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<DashboardOverview />} />
          <Route path="requirement/*" element={<RequirementIntelligencePage />} />

        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default AppRoutes;
