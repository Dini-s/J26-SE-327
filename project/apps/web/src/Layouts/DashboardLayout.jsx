import { useState } from "react";
import { Outlet } from "react-router-dom";
import TopHeader from "./TopHeader";
import Sidebar from "./Sidebar";
import ProjectProvider from "../api/ProjectProvider";

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

        <main className="p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
    </ProjectProvider>
  );
};

export default DashboardLayout;
