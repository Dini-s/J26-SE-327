import React from "react";
import { Lightbulb } from "lucide-react";
import SectionHeader from "./SectionHeader";
import { insights } from "../../data/dashboardData";

const CrossComponentInsights = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <SectionHeader title="Cross-Component Insights" action="View insights" />

      <div className="flex gap-5 p-5">
        <div
          className="
            flex h-16 w-16
            shrink-0
            items-center justify-center
            rounded-full
            bg-indigo-50
            text-indigo-600
          "
        >
          <Lightbulb size={30} strokeWidth={1.5} />
        </div>

        <ul className="space-y-3 pt-1">
          {insights.map((insight) => (
            <li
              key={insight}
              className="
                relative
                pl-4
                text-[11px]
                leading-5
                text-slate-600
              "
            >
              <span className="absolute left-0 top-2 h-1 w-1 rounded-full bg-indigo-600" />

              {insight}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
};

export default CrossComponentInsights;
