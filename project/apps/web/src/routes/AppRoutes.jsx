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
import RepositoryAgentOverView from "../pages/RepositoryAgent/RepositoryAgentOverView";
import ArchitectureVisualization from "../pages/RepositoryAgent/ArchitectureVisualization";
import ArchitectureIssues from "../pages/RepositoryAgent/ArchitectureIssues";
import Dependencies from "../pages/Dependencies";

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<DashboardOverview />} />
          <Route path="repository" element={<RepositoryAgentOverView/>}/>
          <Route path="repository-agent/architecture" element={<ArchitectureVisualization/>}/>
          <Route path="repository-agent/architecture/issues" element={<ArchitectureIssues/>}/>
          <Route path="repository-agent/dependencies" element={<Dependencies/>}/>
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default AppRoutes;
