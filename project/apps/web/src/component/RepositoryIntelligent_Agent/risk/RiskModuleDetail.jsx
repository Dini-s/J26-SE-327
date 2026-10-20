import { MoreVertical, ShieldAlert } from "lucide-react";

import RiskGauge from "./RiskGauge";
import RiskFactorBreakdown from "./RiskFactorBreakdown";
import { useNavigate } from "react-router-dom";

const RiskModuleDetail = ({ module }) => {
  const navigate = useNavigate();

  const moveExplanation = () => {
    navigate(`/repository/ai-explanation?module=${module}`);
  };

  if (!module) {
    return (
      <div className="flex min-h-[500px] items-center justify-center rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-400">
          Select a module to view details
        </p>
      </div>
    );
  }

  return (
    <section
      className="
        rounded-xl
        border border-slate-200
        bg-white
        p-4
        shadow-sm
      "
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-50 text-red-500">
            <ShieldAlert size={19} />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900">
                {module.name}
              </h2>

              <span className="rounded-md bg-red-50 px-2 py-1 text-[10px] font-semibold text-red-500">
                HIGH RISK
              </span>
            </div>

            <p className="mt-1 text-[11px] text-slate-500">{module.package}</p>
          </div>
        </div>

        <button className="text-slate-400 hover:text-slate-700">
          <MoreVertical size={16} />
        </button>
      </div>

      {/* Gauge */}
      <div className="mt-5">
        <h3 className="mb-2 text-[10px] font-semibold text-slate-700">
          Architecture Drift Probability
        </h3>

        <div className="flex items-center">
          <RiskGauge value={module.drift} />

          <div className="ml-2 space-y-4">
            <Detail label="Rank" value="1 / 38" />

            <Detail label="Trend (30d)" value="↗ +14%" danger />

            <Detail label="Last Analyzed" value="May 12, 2025" />

            <Detail label="First Detected" value="Apr 28, 2025" />
          </div>
        </div>
      </div>

      <RiskFactorBreakdown />

      {/* Buttons */}
      <div className="mt-5 flex gap-2">
        <button
          type="button"
          className="
            h-9 flex-1
            rounded-lg
            border border-blue-300
            text-[11px]
            font-medium
            text-blue-600
            transition
            hover:bg-blue-50
          "
        >
          View Module Details
        </button>

        <button
          type="button"
          onClick={moveExplanation}
          className="
            h-9 flex-1
            rounded-lg
            bg-blue-600
            text-[11px]
            font-semibold
            text-white
            transition
            hover:bg-blue-700
          "
        >
          AI Explainer
        </button>
      </div>
    </section>
  );
};

const Detail = ({ label, value, danger }) => (
  <div>
    <p className="text-[10px] text-slate-500">{label}</p>

    <p
      className={`
        mt-0.5 text-[11px] font-semibold
        ${danger ? "text-red-500" : "text-slate-700"}
      `}
    >
      {value}
    </p>
  </div>
);

export default RiskModuleDetail;
