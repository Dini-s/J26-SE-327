import type { ReactNode } from "react";

import {
  Activity,
  BarChart3,
  Bell,
  ChevronDown,
  Circle,
  FileSearch,
  GitBranch,
  Home,
  Menu,
  RefreshCw,
  Settings,
} from "lucide-react";

import { NavLink, Outlet, useLocation } from "react-router-dom";

function navClass({ isActive }: { isActive: boolean }) {
  return `side-sub-link${isActive ? " active" : ""}`;
}

export function AppShell() {
  const location = useLocation();

  const detailsActive = /^\/quality\/requirements\/[^/]+$/.test(
    location.pathname,
  );

  const now = new Date();

  const date = now.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });

  const time = now.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="portal-shell">
      <aside className="portal-sidebar">
        <div className="aspire-brand">
          <div className="aspire-mark">A</div>

          <div>
            <strong>ASPIRE</strong>

            <span>Unified Software Intelligence</span>
          </div>
        </div>

        <div className="research-overview-link">
          <Home size={18} />

          <span>Research Overview</span>
        </div>

        <SidebarHeading>INTELLIGENCE COMPONENTS</SidebarHeading>

        <div className="component-row">
          <span className="component-number green">1</span>

          <span>Requirement Intelligence</span>
        </div>

        <div className="component-row">
          <span className="component-number blue">2</span>

          <span>Repository Intelligence</span>

          <ChevronDown size={14} className="push-right" />
        </div>

        <div className="component-row component-active">
          <span className="component-number purple">3</span>

          <span>Quality & Testing Intelligence</span>

          <ChevronDown size={14} className="push-right" />
        </div>

        <div className="side-subnav">
          <NavLink to="/quality/overview" className={navClass} end>
            <Circle size={9} />
            Overview
          </NavLink>

          <NavLink to="/quality/requirements" className={navClass} end>
            <Circle size={9} />
            Requirements
          </NavLink>

          <NavLink
            to="/quality/requirements/REQ-PET-001"
            className={detailsActive ? "side-sub-link active" : "side-sub-link"}
          >
            <Circle size={9} />
            Requirement Details
          </NavLink>
        </div>

        <div className="component-row">
          <span className="component-number orange">4</span>

          <span>Traceability Intelligence</span>

          <ChevronDown size={14} className="push-right" />
        </div>

        <SidebarHeading>SHARED LAYER</SidebarHeading>

        <SideStatic
          icon={<GitBranch size={16} />}
          label="Unified Software Knowledge Graph"
        />

        <SideStatic
          icon={<FileSearch size={16} />}
          label="Cross-Component Insights"
        />

        <SideStatic
          icon={<BarChart3 size={16} />}
          label="Reports & Analytics"
        />

        <div className="side-subnav shared-report">
          <NavLink to="/quality/reports" className={navClass}>
            <Circle size={9} />
            QA Reports and Analytics
          </NavLink>
        </div>

        <SideStatic icon={<Activity size={16} />} label="Activity Monitor" />

        <SidebarHeading>SYSTEM</SidebarHeading>

        <SideStatic icon={<Settings size={16} />} label="Settings" />

        <div className="repository-card">
          <small>ACTIVE REPOSITORY</small>

          <div className="repo-name-row">
            <div className="repo-icon">S</div>

            <strong>Spring PetClinic</strong>

            <span className="repo-online" />
          </div>

          <div className="repo-separator" />

          <small>Analysis corpus</small>

          <p>Standalone C3 development dataset</p>
        </div>
      </aside>

      <section className="portal-main">
        <header className="portal-header">
          <div className="header-left">
            <Menu className="header-menu" size={25} />

            <div>
              <strong>ASPIRE</strong>

              <span>
                AI Software platform for Intelligence, Reasoning & Evolution
              </span>
            </div>
          </div>

          <div className="header-right">
            <div className="date-time">
              <strong>{date}</strong>

              <span>{time}</span>
            </div>

            <RefreshCw size={22} />

            <div className="bell-wrap">
              <Bell size={22} />
              <span>1</span>
            </div>

            <div className="avatar">PK</div>
          </div>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </section>
    </div>
  );
}

function SidebarHeading({ children }: { children: ReactNode }) {
  return <div className="sidebar-heading">{children}</div>;
}

function SideStatic({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="side-static">
      {icon}
      <span>{label}</span>
    </div>
  );
}
