import { AlertTriangle } from "lucide-react";
const ArchitectureRiskTrend = ({ riskRows = [] }) => {
  const rows = riskRows.filter((r) => r.probability != null).slice(0, 8);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Current Architecture Risk
          </h2>
          <p className="mt-1 text-[11px] text-slate-400">
            Package-level probability from the latest analysis
          </p>
        </div>
      </div>
      {rows.length ? (
        <div className="space-y-3">
          {rows.slice(0, 5).map((row) => {
            const pct = Math.max(
              0,
              Math.min(
                100,
                row.probability <= 1 ? row.probability * 100 : row.probability,
              ),
            );
            return (
              <div key={row.name}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <span className="truncate text-[11px] text-slate-600">
                    {row.name}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-700">
                    {pct.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${pct >= 70 ? "bg-red-500" : pct >= 40 ? "bg-orange-400" : "bg-blue-500"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          <p className="mt-3 flex items-start gap-2 rounded-lg border border-amber-100 bg-amber-50 p-2.5 text-[10px] leading-4 text-amber-800">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            This is a snapshot, not a historical trend. A time-series requires
            saved results from multiple analysis runs.
          </p>
        </div>
      ) : (
        <p className="py-8 text-xs text-slate-500">
          No numeric package risk probabilities were returned.
        </p>
      )}
    </section>
  );
};
export default ArchitectureRiskTrend;
