import MinimalTraceability from "../component/traceability/MinimalTraceability";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import DashboardLayout from "../Layouts/DashboardLayout";
import { pageRoutes } from "./pageRoutes";

const AppRoutes = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          {pageRoutes.map(({ path, Component }) => (
            <Route key={path} path={path.slice(1)} element={path.startsWith("/traceability") ? <MinimalTraceability><Component /></MinimalTraceability> : <Component />} />
          ))}

        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default AppRoutes;
