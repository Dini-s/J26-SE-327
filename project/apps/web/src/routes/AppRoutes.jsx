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
import TraceabilityOverview from "../pages/TraceabilityOverview";
import TraceabilityGraph from "../pages/TraceabilityGraph";
import TraceabilityLink from "../pages/TraceabilityLink";
import TraceabilityChanges from "../pages/TraceabilityChanges";
import TraceabilityAnalytics from "../pages/TraceabilityAnalytics";
import TraceabilityLabeling from "../pages/TraceabilityLabeling";
import KnowledgeGraph from "../pages/KnowledgeGraph";

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<DashboardOverview />} />
          <Route path="traceability" element={<TraceabilityOverview />} />
          <Route path="traceability/graph" element={<TraceabilityGraph />} />
          <Route path="traceability/link" element={<TraceabilityLink />} />
          <Route path="traceability/analytics" element={<TraceabilityAnalytics />} />
          <Route path="traceability/labeling" element={<TraceabilityLabeling />} />
          <Route path="traceability/changes" element={<TraceabilityChanges />} />
          <Route path="knowledge-graph" element={<KnowledgeGraph />} />

        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default AppRoutes;
