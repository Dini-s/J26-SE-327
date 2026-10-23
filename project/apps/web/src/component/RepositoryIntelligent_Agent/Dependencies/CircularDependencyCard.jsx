import { AlertTriangle, Info } from "lucide-react";

const CircularDependencyCard = ({ findings = [] }) => (
  <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-center justify-between gap-2">
      <h2 className="text-sm font-bold text-slate-800">
        Circular Dependency Candidates{" "}
        <span className="font-normal text-slate-400">({findings.length})</span>
      </h2>
      <Info size={14} className="text-slate-400" />
    </div>
    <p className="mt-1 text-xs text-slate-500">
      Only candidates reported by the architecture analyzer are listed.
    </p>
    <div className="mt-3">
      {findings.slice(0, 6).map((item) => (
        <div
          key={
            item.finding_id || `${item.source_package}-${item.target_package}`
          }
          className="flex items-start gap-2 border-b border-slate-100 py-2 last:border-0"
        >
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-500" />
          <div className="min-w-0">
            <p className="break-words text-xs font-medium text-slate-700">
              {item.source_package || "Package group"}
              {item.target_package ? ` → ${item.target_package}` : ""}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              {item.evidence || item.notes || item.finding_id}
            </p>
          </div>
          <span className="shrink-0 rounded bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-700">
            {item.status || "Candidate"}
          </span>
        </div>
      ))}
      {findings.length === 0 && (
        <p className="py-4 text-xs text-slate-400">
          No circular-dependency candidates were reported for this analysis.
          This is not a guarantee that every possible cycle was detected.
        </p>
      )}
    </div>
  </section>
);
export default CircularDependencyCard;
