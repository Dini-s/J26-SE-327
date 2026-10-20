import Settings from "../pages/Settings";
import DashboardOverview from "../pages/DashboardOverview";
import TraceabilityOverview from "../pages/TraceabilityOverview";
import TraceabilityGraph from "../pages/TraceabilityGraph";
import TraceabilityLink from "../pages/TraceabilityLink";
import TraceabilityChanges from "../pages/TraceabilityChanges";
import TraceabilityAnalytics from "../pages/TraceabilityAnalytics";
import TraceabilityLabeling from "../pages/TraceabilityLabeling";
import KnowledgeGraph from "../pages/KnowledgeGraph";


// Shared by the router and sidebar so unfinished items never navigate to missing pages.
export const pageRoutes = [
  { path: "/settings", Component: Settings },
  { path: "/overview", Component: DashboardOverview },
  { path: "/traceability", Component: TraceabilityOverview },
  { path: "/traceability/graph", Component: TraceabilityGraph },
  { path: "/traceability/link", Component: TraceabilityLink },
  { path: "/traceability/changes", Component: TraceabilityChanges },
  { path: "/traceability/analytics", Component: TraceabilityAnalytics },
  { path: "/traceability/labeling", Component: TraceabilityLabeling },
  { path: "/knowledge-graph", Component: KnowledgeGraph },
];
