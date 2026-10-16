import React from "react";
import { ChevronRight } from "lucide-react";

import { architectureChanges } from "../../../data/architectureData";

const dotStyles = {
  red: "bg-red-500",
  orange: "bg-orange-400",
  green: "bg-emerald-500",
};

const RecentArchitectureChanges = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-bold text-slate-900">
          Recent Architecture Changes
        </h2>

        <button className="text-[9px] font-medium text-blue-600">
          View All
        </button>
      </div>

      <div className="mt-4 space-y-4">
        {architectureChanges.map((change) => (
          <div key={change.text} className="flex items-start gap-2">
            <span
              className={`
                  mt-1
                  h-2 w-2
                  shrink-0
                  rounded-full
                  ${dotStyles[change.type]}
                `}
            />

            <p className="flex-1 text-[9px] text-slate-600">{change.text}</p>

            <span className="whitespace-nowrap text-[9px] text-slate-400">
              {change.time}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default RecentArchitectureChanges;
