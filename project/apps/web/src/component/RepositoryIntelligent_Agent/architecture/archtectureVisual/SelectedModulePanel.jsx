
import {
  AlertTriangle,
  ChevronRight,
  GitBranch,
  Network,
  ShieldAlert,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import RiskScoreGauge from "./RiskScoreGauge";

const formatNumber = (value, digits = 2) => {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
};

const SelectedModulePanel = ({ module, edges = [] }) => {
  const navigate = useNavigate();

  
  
const dependencies = !module?.id
  ? []
  : edges
      .filter((edge) => edge.source === module.id)
      .map((edge) => ({
        id: edge.id,
        name: edge.targetName || edge.target,
      }));



  if (!module) {
    return (
      <aside className="rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-sm font-semibold text-slate-800">
          Package details
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Select a package from the architecture graph to inspect its metrics.
        </p>
      </aside>
    );
  }

  const hasProxyScore = Number.isFinite(Number(module.proxyProbability));
  const score = hasProxyScore
    ? Math.round(Number(module.proxyProbability) * 100)
    : null;

  return (
    <aside className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
          <ShieldAlert size={18} />
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="break-words text-sm font-bold text-slate-900">
            {module.name}
          </h2>
          <p className="mt-1 break-all text-[11px] text-slate-500">
            {module.package || module.name}
          </p>
          <span className="mt-2 inline-flex rounded-md bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-600">
            {module.layer || "Package"}
          </span>
        </div>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <h3 className="text-xs font-semibold text-slate-800">
          Architecture metrics
        </h3>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <Metric label="Java files" value={module.javaFiles} />
          <Metric label="Lines of code" value={module.linesOfCode} />
          <Metric label="Fan-in" value={module.fanIn} />
          <Metric label="Fan-out" value={module.fanOut} />
          <Metric label="Total coupling" value={module.totalCoupling} />
          <Metric
            label="Instability"
            value={formatNumber(module.instability)}
          />
        </div>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <h3 className="text-xs font-semibold text-slate-800">
          HRIM architecture-change proxy
        </h3>

        {hasProxyScore ? (
          <>
            <div className="mt-3 flex items-center gap-4">
              <RiskScoreGauge value={score} />
              <div className="min-w-0">
                <p className="text-2xl font-bold text-slate-900">
                  {score}%
                </p>
                <p className="mt-1 text-[11px] text-slate-500">
                  Exploratory proxy score
                </p>
                <p className="mt-1 text-[11px] text-slate-600">
                  Model label: {module.predictedProxyLabel ?? "Unavailable"}
                </p>
              </div>
            </div>

            <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <AlertTriangle
                size={14}
                className="mt-0.5 shrink-0 text-amber-600"
              />
              <p className="text-[11px] leading-5 text-amber-800">
                This is an exploratory architecture-change proxy, not a
                confirmed architecture violation or a validated probability
                of architectural drift.
              </p>
            </div>
          </>
        ) : (
          <p className="mt-2 text-xs text-slate-500">
            No proxy prediction is available for this package.
          </p>
        )}
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="flex items-center gap-2">
          <Network size={14} className="text-slate-500" />
          <h3 className="text-xs font-semibold text-slate-800">
            Outgoing dependencies
          </h3>
          <span className="ml-auto rounded-md bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
            {dependencies.length}
          </span>
        </div>

        {dependencies.length ? (
          <div className="mt-3 space-y-2">
            {dependencies.map((dependency) => (
              <div
                key={dependency.id}
                className="flex min-w-0 items-start gap-2 rounded-lg bg-slate-50 px-3 py-2"
              >
                <GitBranch
                  size={12}
                  className="mt-0.5 shrink-0 text-slate-500"
                />
                <span className="break-all text-[11px] text-slate-700">
                  {dependency.name}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-slate-500">
            No outgoing dependencies were found for this package in the
            returned dependency data.
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={() => navigate("/repository/issues")}
        className="mt-5 flex items-center gap-1 border-t border-slate-100 pt-4 text-xs font-medium text-indigo-600 transition hover:text-indigo-800"
      >
        View architecture issues
        <ChevronRight size={14} />
      </button>
    </aside>
  );
};

const Metric = ({ label, value }) => (
  <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
    <p className="text-[10px] text-slate-500">{label}</p>
    <p className="mt-1 break-words text-sm font-semibold text-slate-800">
      {value ?? "—"}
    </p>
  </div>
);

export default SelectedModulePanel;
