import { useState } from "react";
import { Outlet } from "react-router-dom";
import TopHeader from "./TopHeader";
import Sidebar from "./Sidebar";
import ProjectProvider from "../api/ProjectProvider";
import { GlobalActivity } from "../component/traceability/Activity";

const DashboardLayout = () => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <ProjectProvider>
    <div className="min-h-screen bg-slate-50">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
      />

      <div
        className={`
          min-h-screen
          transition-all duration-300
          ${collapsed ? "ml-[72px]" : "ml-[260px]"}
        `}
      >
        <TopHeader onMenuClick={() => setCollapsed(!collapsed)} />

        <main className="c4-main-canvas min-h-[calc(100vh-64px)] px-4 py-5 sm:px-7 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
    <GlobalActivity />
    </ProjectProvider>
  );
};

export default DashboardLayout;
