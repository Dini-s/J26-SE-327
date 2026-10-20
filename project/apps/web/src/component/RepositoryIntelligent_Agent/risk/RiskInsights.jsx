import { ChevronRight } from "lucide-react";

import { riskInsights } from "../../../data/riskModules";

const dotStyles = {
  red: "bg-red-500",
  orange: "bg-orange-400",
  green: "bg-emerald-500",
};

const RiskInsights = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-xs font-semibold text-slate-900">Insights</h2>

      <div className="mt-4 space-y-5">
        {riskInsights.map((insight) => (
          <div key={insight.text} className="flex gap-3">
            <span
              className={`
                  mt-1
                  h-2 w-2
                  shrink-0
                  rounded-full
                  ${dotStyles[insight.type]}
                `}
            />

            <p className="text-[11px] leading-4 text-slate-600">
              {insight.text}
            </p>
          </div>
        ))}
      </div>

      <button
        type="button"
        className="
          mt-5
          flex items-center gap-1
          text-[11px]
          font-medium
          text-blue-600
        "
      >
        View All Insights
        <ChevronRight size={12} />
      </button>
    </section>
  );
};

export default RiskInsights;
