import {
  Activity,
  GitCommit,
  FileCode2,
  TrendingUp,
  GitPullRequest,
} from "lucide-react";
const icons = [Activity, GitCommit, FileCode2, TrendingUp, GitPullRequest];
const RepositoryEvolution = ({ metrics = [] }) => (
  <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold text-slate-900">
        Repository Evolution Overview
      </h2>
      <span className="text-[10px] text-slate-400">Latest analysis</span>
    </div>
    <div className="space-y-3">
      {metrics.map((item, index) => {
        const Icon = icons[index % icons.length];
        return (
          <div key={item.label} className="flex items-center gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
              <Icon size={14} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold text-slate-700">
                {item.label}
              </p>
              <p className="text-[10px] text-slate-400">
                Repository history metrics
              </p>
            </div>
            <strong className="w-16 text-right text-xs text-slate-800">
              {item.value == null ? "—" : Number(item.value).toLocaleString()}
            </strong>
          </div>
        );
      })}
    </div>
    <p className="mt-3 text-[10px] leading-4 text-slate-400">
      Metrics are shown only when returned by the API. Historical sparklines
      require stored snapshots over time.
    </p>
  </section>
);
export default RepositoryEvolution;
