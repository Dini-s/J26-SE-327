import { Info } from "lucide-react";
import { modelMetrics } from "../../../data/repositoryData";

const HRIMModelSummary = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-1">
        <h2 className="text-sm font-semibold text-slate-900">
          HRIM Model Summary
        </h2>

        <Info size={12} className="text-slate-400" />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-6">
        <Metric label="Model" value={modelMetrics.model} />

        <Metric label="Accuracy" value={modelMetrics.accuracy} />

        <Metric label="Precision" value={modelMetrics.precision} />

        <Metric label="Recall" value={modelMetrics.recall} />

        <Metric label="F1-Score" value={modelMetrics.f1Score} />

        <Metric label="Last Trained" value={modelMetrics.lastTrained} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Tag>Semantic Features</Tag>

        <Tag>Evolution Features</Tag>

        <Tag>Software Metrics</Tag>

        <Tag>Graph Features</Tag>
      </div>
    </section>
  );
};

const Metric = ({ label, value }) => (
  <div>
    <p className="text-[10px] text-slate-400">{label}</p>

    <p className="mt-1 text-xs font-semibold text-slate-800">{value}</p>
  </div>
);

const Tag = ({ children }) => (
  <span className="rounded-md bg-indigo-50 px-2 py-1 text-[10px] font-medium text-indigo-600">
    {children}
  </span>
);

export default HRIMModelSummary;
