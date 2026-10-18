import { useState } from "react";

import {
  CalendarDays,
  ChevronDown,
  Database,
  Filter,
  Menu,
  Play,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { dependencyStats } from "../data/dependenciesData";
import DependencyStatCard from "../component/RepositoryIntelligent_Agent/Dependencies/DependencyStatCard";
import DependencyTabs from "../component/RepositoryIntelligent_Agent/Dependencies/DependencyTabs";
import DependencyLegend from "../component/RepositoryIntelligent_Agent/Dependencies/DependencyLegend";
import DependencyGraph from "../component/RepositoryIntelligent_Agent/Dependencies/DependencyGraph";
import CircularDependencyCard from "../component/RepositoryIntelligent_Agent/Dependencies/CircularDependencyCard";
import SelectedModule from "../component/RepositoryIntelligent_Agent/Dependencies/SelectedModule";


const Dependencies = () => {
  const [activeTab, setActiveTab] = useState("Dependency Graph");
  const [selectedNode, setSelectedNode] = useState(null);

  return (
    <div className="w-full space-y-3">
      {/* HEADER */}

      <header className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Dependencies
          </h1>

          <p className="mt-1 text-[12px] text-slate-500">
            Analyze and explore module dependencies, coupling, and dependency
            health across the repository.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-medium text-slate-700 shadow-sm">
            <Database size={13} />
            Spring PetClinic
            <ChevronDown size={11} />
          </button>

          <button className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-medium text-slate-700 shadow-sm">
            <CalendarDays size={12} />
            May 12, 2025
            <span className="text-slate-400">09:45 AM</span>
          </button>

          <button className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-medium text-slate-700">
            <RefreshCw size={12} />
            Refresh
          </button>

          <button className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-[11px] font-semibold text-white shadow-sm hover:bg-blue-700">
            <Play size={11} />
            Analyze Repository
          </button>
        </div>
      </header>

      {/* KPI CARDS */}

      <section className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {dependencyStats.map((stat) => (
          <DependencyStatCard key={stat.title} stat={stat} />
        ))}
      </section>

      {/* MAIN */}

      <section className="grid grid-cols-1 gap-3 xl:grid-cols-[1.55fr_0.85fr]">
        {/* GRAPH */}

        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <DependencyTabs activeTab={activeTab} onChange={setActiveTab} />

          {/* Toolbar */}

          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 p-2">
            <div className="flex gap-2">
              <button className="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 text-[12px] text-slate-600">
                View: Module View
                <ChevronDown size={10} />
              </button>

              <button className="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 text-[12px] text-slate-600">
                Layout: Hierarchical
                <ChevronDown size={10} />
              </button>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center rounded-md border border-slate-200 px-2 py-1.5">
                <Search size={10} className="text-slate-400" />

                <input
                  placeholder="Search modules..."
                  className="ml-2 w-28 bg-transparent text-[12px] outline-none"
                />
              </div>

              <button className="flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1.5 text-[12px]">
                <Filter size={10} />
                Filters
              </button>

              <button className="rounded-md border border-slate-200 p-1.5">
                <SlidersHorizontal size={11} />
              </button>
            </div>
          </div>

          {/* Graph */}

          <div className="relative">
            <DependencyLegend />

            <DependencyGraph onNodeSelect={setSelectedNode} />
          </div>
        </section>

        {/* SELECTED MODULE */}

        <SelectedModule/>
      </section>

      {/* BOTTOM */}

      <section className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        <CircularDependencyCard />

        <HighDependencyPlaceholder />

        <OrphanPlaceholder />
      </section>
    </div>
  );
};

const HighDependencyPlaceholder = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h2 className="text-[12px] font-bold text-slate-800">
        High Dependency Modules
      </h2>

      <div className="mt-3 space-y-2">
        {[
          ["OwnerService", 9, 14, "0.61", "High"],
          ["PetService", 8, 12, "0.60", "High"],
          ["VisitService", 7, 10, "0.59", "Medium"],
          ["OrderService", 6, 9, "0.60", "Medium"],
          ["ReportService", 5, 8, "0.62", "Medium"],
        ].map(([name, ca, ce, instability, risk]) => (
          <div
            key={name}
            className="grid grid-cols-[1.3fr_0.5fr_0.5fr_0.6fr_0.5fr] items-center border-b border-slate-100 py-2 text-[11px]"
          >
            <span className="font-medium text-slate-700">{name}</span>

            <span>{ca}</span>

            <span>{ce}</span>

            <span>{instability}</span>

            <span
              className={risk === "High" ? "text-red-500" : "text-orange-500"}
            >
              {risk}
            </span>
          </div>
        ))}
      </div>

      <button className="mt-3 text-[12px] font-semibold text-blue-600">
        View All High Dependency Modules →
      </button>
    </section>
  );
};

const OrphanPlaceholder = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h2 className="text-[12px] font-bold text-slate-800">
        Orphan / Unused Modules (8)
      </h2>

      <div className="mt-3 space-y-3">
        {[
          ["OldReportGenerator", "No incoming dependencies"],
          ["LegacyExportService", "Not used by any module"],
          ["TestDataBuilder", "Not used in production code"],
          ["DummyPaymentGateway", "No incoming dependencies"],
        ].map(([name, issue]) => (
          <div
            key={name}
            className="flex items-center justify-between border-b border-slate-100 pb-2"
          >
            <span className="text-[12px] font-medium text-slate-700">
              {name}
            </span>

            <span className="text-[11px] text-slate-400">{issue}</span>
          </div>
        ))}
      </div>

      <button className="mt-3 text-[12px] font-semibold text-blue-600">
        View All Orphan Modules →
      </button>
    </section>
  );
};

export default Dependencies;
