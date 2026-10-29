
import { useState } from "react";
import { Outlet } from "react-router-dom";
import TopHeader from "./TopHeader";
import Sidebar from "./Sidebar";
import RepositoryProvider from "../context/RepositoryProvider";

const DashboardLayout = () => {
  const [collapsed, setCollapsed] = useState(false);

  const { pathname } = useLocation();
  const title = pathname.startsWith("/quality/requirements/") ? "Requirement Details"
    : pathname.startsWith("/quality/requirements") ? "Quality Requirements"
    : pathname.startsWith("/quality/reports") ? "QA Reports & Analytics"
    : pathname.startsWith("/quality") ? "Quality & Testing Intelligence" : "Research Overview";

  return (
    <RepositoryProvider>
      <div className="min-h-screen bg-slate-50">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed(!collapsed)}
        />

        <div
          className={`min-h-screen transition-all duration-300 ${
            collapsed ? "ml-[72px]" : "ml-[260px]"
          }`}
        >
          <TopHeader title={title} sidebarCollapsed={collapsed} onMenuClick={() => setCollapsed(!collapsed)} />

          <main className="p-4 sm:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </RepositoryProvider>
  );
};

export default DashboardLayout;
