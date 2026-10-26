
import { useMemo } from "react";
import { ArrowUpRight } from "lucide-react";

const TopRiskPackages = ({ modules = [] }) => {
  const packages = useMemo(
    () =>
      modules
        .filter(
          (module) =>
            typeof module.proxyProbability === "number" &&
            Number.isFinite(module.proxyProbability) &&
            module.proxyProbability >= 0 &&
            module.proxyProbability <= 1
        )
        .slice()
        .sort((a, b) => b.proxyProbability - a.proxyProbability)
        .slice(0, 5),
    [modules]
  );

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h3 className="text-base font-semibold text-slate-900">
          Highest Proxy Scores
        </h3>

        <p className="mt-1 text-sm text-slate-500">
          Packages ranked by their current exploratory HRIM output
        </p>
      </div>

      {packages.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Run an analysis to view package scores.
        </p>
      ) : (
        <div className="space-y-4">
          {packages.map((module, index) => (
            <div
              key={module.id ?? module.package}
              className="flex items-center gap-3"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-sm font-semibold text-slate-600">
                {index + 1}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className="truncate text-sm font-medium text-slate-900"
                  title={module.name}
                >
                  {module.name}
                </p>

                <p
                  className="truncate text-xs text-slate-500"
                  title={module.package}
                >
                  {module.package}
                </p>

                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                    style={{
                      width: `${module.proxyProbability * 100}%`,
                    }}
                  />
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-1 text-sm font-semibold text-slate-900">
                {(module.proxyProbability * 100).toFixed(2)}%
                <ArrowUpRight
                  size={14}
                  className="text-indigo-500"
                  aria-hidden="true"
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="mt-4 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
        Rankings reflect current exploratory proxy scores, not confirmed
        architecture drift.
      </p>
    </section>
  );
};

export default TopRiskPackages;
