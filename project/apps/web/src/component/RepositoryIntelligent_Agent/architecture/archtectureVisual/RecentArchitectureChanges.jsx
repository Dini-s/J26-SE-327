
import { History, Info } from "lucide-react";

const RecentArchitectureChanges = ({ changes }) => {
  const hasChangeHistory = Array.isArray(changes);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <History size={15} className="text-slate-500" />
          <h2 className="text-[11px] font-bold text-slate-900">
            Recent Architecture Changes
          </h2>
        </div>
      </div>

      {!hasChangeHistory ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-start gap-2">
            <Info size={15} className="mt-0.5 shrink-0 text-slate-500" />
            <div>
              <p className="text-xs font-medium text-slate-700">
                Change history unavailable
              </p>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">
                The current API response does not include a chronological
                architecture-change history. Repository evolution metrics
                alone do not establish when architecture changes occurred.
              </p>
            </div>
          </div>
        </div>
      ) : changes.length === 0 ? (
        <div className="mt-4 py-5 text-center">
          <p className="text-xs font-medium text-slate-700">
            No changes returned
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            No architecture-change records were supplied.
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {changes.map((change, index) => (
            <div
              key={change.id ?? `${change.text}-${index}`}
              className="flex items-start gap-2"
            >
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-indigo-500" />

              <p className="min-w-0 flex-1 text-[11px] text-slate-600">
                {change.text}
              </p>

              {change.time && (
                <span className="whitespace-nowrap text-[10px] text-slate-400">
                  {change.time}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

export default RecentArchitectureChanges;
