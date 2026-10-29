import { lazy, Suspense } from "react";

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import DashboardLayout from "../Layouts/DashboardLayout";
import DashboardOverview from "../pages/DashboardOverview";
import RepositoryAgentOverView from "../pages/RepositoryAgent/RepositoryAgentOverView";
import ArchitectureVisualization from "../pages/RepositoryAgent/ArchitectureVisualization";
import ArchitectureIssues from "../pages/RepositoryAgent/ArchitectureIssues";
import Dependencies from "../pages/RepositoryAgent/Dependencies";
import Repositories from "../pages/RepositoryAgent/Repositories";
import RiskModules from "../pages/RepositoryAgent/RiskModels";
import EvolutionOverview from "../pages/RepositoryAgent/EvolutionOverview";

import QualityLayout from "../Layouts/QualityLayout.jsx";
const QualityApp = lazy(() => import("../component/quality/QualityApp.jsx"));

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<DashboardOverview />} />
          <Route path="quality/*" element={<QualityLayout><Suspense fallback={<p role="status">Loading quality intelligence...</p>}><QualityApp /></Suspense></QualityLayout>} />
          <Route path="repository" element={<RepositoryAgentOverView />} />
          <Route
            path="repository-agent/architecture"
            element={<ArchitectureVisualization />}
          />
          <Route
            path="repository-agent/architecture/issues"
            element={<ArchitectureIssues />}
          />
          <Route
            path="repository-agent/dependencies"
            element={<Dependencies />}
          />
          <Route
            path="repository-agent/repository"
            element={<Repositories />}
          />
          <Route path="repository-agent/riskModule" element={<RiskModules />} />
          <Route
            path="repository-agent/evolution"
            element={<EvolutionOverview />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default AppRoutes;
