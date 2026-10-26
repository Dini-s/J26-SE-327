
import { ShieldCheck, Info } from "lucide-react";

const ViolationOverview = ({ violations }) => {
  const hasViolationData = Array.isArray(violations);

  const totalViolations = hasViolationData
    ? violations.length
    : null;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs font-bold text-slate-900">
          Violation Overview
        </h2>

        <ShieldCheck size={16} className="text-slate-400" />
      </div>

      {!hasViolationData ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-start gap-2">
            <Info size={16} className="mt-0.5 shrink-0 text-slate-500" />
            <div>
              <p className="text-sm font-medium text-slate-700">
                No validated violation data
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                The current analysis API does not report confirmed
                architecture violations. Proxy predictions are not
                violation detections.
              </p>
            </div>
          </div>
        </div>
      ) : totalViolations === 0 ? (
        <div className="mt-4 py-5 text-center">
          <p className="text-2xl font-bold text-slate-900">0</p>
          <p className="mt-1 text-xs text-slate-500">
            No violations were returned by the supplied data.
          </p>
        </div>
      ) : (
        <div className="mt-4">
          <p className="text-2xl font-bold text-slate-900">
            {totalViolations}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Reported violation records
          </p>
        </div>
      )}
    </section>
  );
};

export default ViolationOverview;
