import React from "react";
import SectionHeader from "./SectionHeader";
import AgentCard from "./AgentCard";
import { agents } from "../../data/dashboardData";

const IntelligenceAgents = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <SectionHeader title="Intelligence Agents" />

      <div className="grid grid-cols-1 sm:grid-cols-2">
        {agents.map((agent) => (
          <AgentCard key={agent.name} {...agent} />
        ))}
      </div>
    </section>
  );
};

export default IntelligenceAgents;
