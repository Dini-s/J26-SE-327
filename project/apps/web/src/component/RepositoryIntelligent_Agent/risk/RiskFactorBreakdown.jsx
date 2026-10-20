import { riskFactors } from "../../../data/riskModules";

const colors = {
  high: "bg-red-500",
  medium: "bg-orange-400",
  low: "bg-emerald-500",
};

const textColors = {
  high: "text-red-500",
  medium: "text-orange-500",
  low: "text-emerald-600",
};

const RiskFactorBreakdown = () => {
  return (
    <div className="border-t border-slate-100 pt-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[11px] font-semibold text-slate-800">
          Risk Factor Breakdown
          <span className="ml-1 text-slate-400">ⓘ</span>
        </h3>

        <button className="text-[11px] font-medium text-blue-600 border border-ai-secondary p-2 rounded-xl">
          View SHAP Explanation
        </button>
      </div>

      <div className="space-y-3">
        {riskFactors.map((factor) => (
          <div
            key={factor.name}
            className="grid grid-cols-[1fr_1.3fr_auto_auto] items-center gap-2"
          >
            <span className="text-[11px] text-slate-600">{factor.name}</span>

            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`
                  h-full
                  rounded-full
                  ${colors[factor.type]}
                `}
                style={{
                  width: `${factor.value * 300}%`,
                }}
              />
            </div>

            <span className="text-[11px] font-semibold text-slate-700">
              {factor.value.toFixed(2)}
            </span>

            <span
              className={`
                w-12 text-right text-[10px]
                ${textColors[factor.type]}
              `}
            >
              {factor.level}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RiskFactorBreakdown;
