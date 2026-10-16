import React from "react";
import SectionHeader from "./SectionHeader";
import ComponentStatusCard from "./ComponentStatusCard";
import { intelligenceComponents } from "../../data/dashboardData";

const IntelligenceComponents = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <SectionHeader title="Intelligence Components Status" />

      <div className="grid grid-cols-1 md:grid-cols-2">
        {intelligenceComponents.map((component) => (
          <ComponentStatusCard key={component.number} {...component} />
        ))}
      </div>
    </section>
  );
};

export default IntelligenceComponents;
