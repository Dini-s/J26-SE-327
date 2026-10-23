
import { GitBranch, ShieldAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";

import RiskGauge from "./RiskGauge";

const RiskModuleDetail = ({ module }) => {
  const navigate = useNavigate();

  if (!module) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-400">
          Select a package to view its analysis
        </p>
      </div>
    );
  }

  const probability = module.proxyProbability;
  const scoreAvailable = typeof probability === "number";

  const handleExplanation = () => {
    navigate(
      `/repository/ai-explanation?module=${encodeURIComponent(
        module.package
      )}`
    );
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
          <ShieldAlert size={19} />
        </div>

        <div className="min-w-0">
          <h2 className="break-words text-sm font-bold text-slate-900">
            {module.name}
          </h2>

          <p className="mt-1 break-all text-[11px] text-slate-500">
            {module.package}
          </p>
        </div>
      </div>

      <div className="mt-5 rounded-lg bg-slate-50 p-3">
        <h3 className="text-xs font-semibold text-slate-700">
          Architecture Change Proxy Score
        </h3>

        {scoreAvailable ? (
          <>
            <RiskGauge value={probability * 100} />

            <p className="mt-2 text-center text-[11px] text-slate-500">
              Predicted proxy label:{" "}
              <span className="font-semibold text-slate-700">
                {module.predictionLabel ?? "—"}
              </span>
            </p>
          </>
        ) : (
          <p className="py-8 text-center text-sm text-slate-500">
            No proxy prediction is available for this package.
          </p>
        )}
      </div>

      <div className="mt-4">
        <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-800">
          <GitBranch size={14} />
          Structural Metrics
        </h3>

        <div className="grid grid-cols-2 gap-3">
          <Detail label="Java Files" value={module.javaFiles} />
          <Detail label="Lines of Code" value={module.linesOfCode} />
          <Detail label="Fan-in" value={module.fanIn} />
          <Detail label="Fan-out" value={module.fanOut} />
          <Detail label="Total Coupling" value={module.fanIn + module.fanOut} />
          <Detail
            label="Instability"
            value={
              module.instability == null
                ? "—"
                : Number(module.instability).toFixed(2)
            }
          />
        </div>
      </div>

      <div className="mt-5">
        <button
          type="button"
          onClick={handleExplanation}
          className="h-9 w-full rounded-lg bg-blue-600 text-xs font-semibold text-white transition hover:bg-blue-700"
        >
          Open AI Explainer
        </button>
      </div>
    </section>
  );
};

const Detail = ({ label, value }) => (
  <div className="rounded-lg border border-slate-100 p-3">
    <p className="text-[10px] text-slate-500">{label}</p>
    <p className="mt-1 break-words text-sm font-semibold text-slate-800">
      {value ?? "—"}
    </p>
  </div>
);

export default RiskModuleDetail;
