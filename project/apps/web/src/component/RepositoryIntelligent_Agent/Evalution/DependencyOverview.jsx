import { AlertTriangle, Boxes, ExternalLink, GitBranch } from "lucide-react";

import { dependencies } from "../../../data/evolutionData";

const icons = [Boxes, GitBranch, ExternalLink, AlertTriangle];

const DependencyOverview = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-xs font-bold text-slate-900">Dependency Overview</h2>

      <div className="mt-4 space-y-3">
        {dependencies.map((dependency, index) => {
          const Icon = icons[index];

          return (
            <div
              key={dependency.name}
              className="flex items-center justify-between border-b border-slate-50 pb-2"
            >
              <div className="flex items-center gap-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-purple-50 text-purple-600">
                  <Icon size={12} />
                </div>

                <span className="text-[10px] text-slate-600">
                  {dependency.name}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold text-slate-700">
                  {dependency.value}
                </span>

                {dependency.percent && (
                  <span className="text-[9px] text-slate-400">
                    ({dependency.percent})
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <button className="mt-4 text-[10px] font-medium text-blue-600">
        View Dependency Analysis →
      </button>
    </section>
  );
};

export default DependencyOverview;
