import { Box } from "lucide-react";

const ModuleHeader = ({ module }) => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-6">
        {/* Module */}
        <div className="flex items-center gap-3 xl:col-span-1">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-50 text-red-500">
            <Box size={20} />
          </div>

          <div>
            <span className="rounded bg-red-50 px-2 py-1 text-[10px] font-semibold text-red-500">
              High Risk
            </span>

            <h2 className="mt-1 text-[15px] font-bold text-slate-900">
              {module.name}
            </h2>

            <p className="text-[10px] text-slate-500">{module.package}</p>
          </div>
        </div>

        <Metric
          label="Drift Probability (HRIM)"
          value={module.driftProbability}
          change="↑ 0.18 vs last analysis"
          danger
        />

        <Metric
          label="Risk Level"
          value={module.riskLevel}
          change="↑ Increased"
          danger
        />

        <Metric
          label="Architecture Health"
          value={module.architectureHealth}
          suffix="/ 100"
          change="↓ 10 vs last analysis"
          danger
        />

        <Metric
          label="Confidence Score"
          value={`${module.confidence}%`}
          progress={module.confidence}
        />

        <div>
          <p className="text-[10px] text-slate-500">Analysis ID</p>

          <p className="mt-1 text-[11px] font-bold text-slate-800">
            {module.analysisId}
          </p>

          <p className="mt-4 text-[10px] text-slate-500">Model</p>

          <p className="text-[11px] font-semibold text-slate-700">
            {module.model}
          </p>
        </div>
      </div>
    </section>
  );
};

const Metric = ({ label, value, suffix, change, danger, progress }) => {
  return (
    <div className="border-l border-slate-100 pl-4">
      <p className="text-[10px] text-slate-500">{label}</p>

      <p
        className={`mt-1 text-xl font-bold ${
          danger && label === "Risk Level" ? "text-red-500" : "text-slate-900"
        }`}
      >
        {value}

        {suffix && (
          <span className="ml-1 text-[11px] font-medium text-slate-500">
            {suffix}
          </span>
        )}
      </p>

      {progress !== undefined && (
        <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-emerald-500"
            style={{
              width: `${progress}%`,
            }}
          />
        </div>
      )}

      {change && (
        <p
          className={`mt-1 text-[10px] font-medium ${
            danger ? "text-red-500" : "text-emerald-600"
          }`}
        >
          {change}
        </p>
      )}
    </div>
  );
};

export default ModuleHeader;
