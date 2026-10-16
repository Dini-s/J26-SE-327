import { ArrowUpRight, ArrowDown, Info } from "lucide-react";
import { highRiskModules } from "../../../data/repositoryData";

const riskStyles = {
  HIGH: "bg-red-50 text-red-600",
  MEDIUM: "bg-orange-50 text-orange-600",
  LOW: "bg-emerald-50 text-emerald-600",
};

const HighRiskModules = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-1.5">
          <h2 className="text-sm font-semibold text-slate-900">
            Top High-Risk Modules
          </h2>

          <Info size={12} className="text-slate-400" />
        </div>

        <button className="text-[11px] font-medium text-indigo-600">
          View All
        </button>
      </div>

      {/* Header */}
      <div className="grid grid-cols-[1.5fr_0.7fr_0.7fr_0.4fr] bg-slate-50 px-3 py-2 text-[10px] font-medium text-slate-500">
        <span>Module</span>
        <span>Risk Level</span>
        <span>Drift Probability</span>
        <span>Trend</span>
      </div>

      {/* Rows */}
      {highRiskModules.map((module) => (
        <div
          key={module.name}
          className="
            grid
            grid-cols-[1.5fr_0.7fr_0.7fr_0.4fr]
            items-center
            border-b
            border-slate-100
            px-3
            py-3
          "
        >
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
              ◈
            </div>

            <div className="min-w-0">
              <p className="truncate text-[11px] font-semibold text-slate-700">
                {module.name}
              </p>

              <p className="truncate text-[10px] text-slate-400">
                {module.package}
              </p>
            </div>
          </div>

          <span
            className={`
              w-fit
              rounded-md
              px-2 py-1
              text-[10px]
              font-semibold
              ${riskStyles[module.risk]}
            `}
          >
            {module.risk}
          </span>

          <span className="text-[11px] font-semibold text-slate-700">
            {module.drift}
          </span>

          <div>
            {module.trend === "down" ? (
              <ArrowDown size={14} className="text-emerald-500" />
            ) : (
              <ArrowUpRight size={14} className="text-red-500" />
            )}
          </div>
        </div>
      ))}
    </section>
  );
};

export default HighRiskModules;
