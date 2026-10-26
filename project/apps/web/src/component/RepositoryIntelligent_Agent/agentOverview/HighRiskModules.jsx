import { ArrowUpRight, ArrowDown, Info } from "lucide-react";
const riskStyles = {
  HIGH: "bg-red-50 text-red-600",
  MEDIUM: "bg-orange-50 text-orange-600",
  LOW: "bg-emerald-50 text-emerald-600",
  UNKNOWN: "bg-slate-100 text-slate-600",
};
const HighRiskModules = ({ riskRows = [] }) => {
  const rows = riskRows.slice(0, 5);
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          Top Risk Packages <Info size={12} className="text-slate-400" />
        </h2>
        <span className="text-[10px] text-slate-400">Backend results</span>
      </div>
      <div className="grid grid-cols-[1.5fr_0.7fr_0.7fr_0.4fr] bg-slate-50 px-3 py-2 text-[10px] font-medium text-slate-500">
        <span>Package</span>
        <span>Risk</span>
        <span>Probability</span>
        <span> </span>
      </div>
      {rows.length ? (
        rows.map((row, i) => (
          <div
            key={`${row.name}-${i}`}
            className="grid grid-cols-[1.5fr_0.7fr_0.7fr_0.4fr] items-center gap-1 border-b border-slate-100 px-3 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-[11px] font-semibold text-slate-700">
                {row.name}
              </p>
              <p className="truncate text-[10px] text-slate-400">
                {row.package}
              </p>
            </div>
            <span
              className={`w-fit rounded-md px-2 py-1 text-[10px] font-semibold ${riskStyles[row.risk] || riskStyles.UNKNOWN}`}
            >
              {row.risk}
            </span>
            <span className="text-[11px] font-semibold text-slate-700">
              {row.probability == null
                ? "—"
                : `${(row.probability <= 1 ? row.probability * 100 : row.probability).toFixed(1)}%`}
            </span>
            {row.probability == null ? null : row.probability >= 0.7 ? (
              <ArrowUpRight size={14} className="text-red-500" />
            ) : (
              <ArrowDown size={14} className="text-emerald-500" />
            )}
          </div>
        ))
      ) : (
        <p className="p-4 text-xs text-slate-500">
          No package-level risk predictions were returned by the backend.
        </p>
      )}
    </section>
  );
};
export default HighRiskModules;
