import React from "react";
import ContentHeader from "../component/common/ContentHeader";
import { stats } from "../data/dashboardData";
import StatCard from "../component/dashboard/StatsCard";
import IntelligenceComponents from "../component/dashboard/IntelligenceComponents";
import IntelligenceAgents from "../component/dashboard/IntelligenceAgents";
import CrossComponentInsights from "../component/dashboard/CrossComponentInsights";
import KnowledgeGraphCard from "../component/dashboard/KnowledgeGraphCard";
import IntelligenceAlerts from "../component/dashboard/IntelligenceAlerts";
import RecentActivity from "../component/dashboard/RecentActivity";

const DashboardOverview = () => {
  return (
    <div className="mx-auto w-full max-w-[1500px]">
      <ContentHeader title={"Framework Overview"} subtitle={""} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <IntelligenceComponents />

        <IntelligenceAgents />
      </div>

      <div className="mt-5">
        <CrossComponentInsights />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <KnowledgeGraphCard />

        <div className="space-y-5">
          <IntelligenceAlerts />
          <RecentActivity />
        </div>
      </div>

      <footer className="py-8 text-center">
        <p className="text-[10px] text-slate-400">
          © 2026 ASPIRE Framework. All rights reserved.
        </p>
      </footer>
    </div>
  );
};

export default DashboardOverview;
