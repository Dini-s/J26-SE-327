import { GitCommit } from "lucide-react";
const RecentCodeChanges = ({ changes = [] }) => (
  <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
    <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
      <h2 className="text-sm font-semibold text-slate-900">
        Recent Code Changes
      </h2>
      <span className="text-[10px] text-slate-400">File evolution data</span>
    </div>
    {changes.length ? (
      changes.map((change, i) => (
        <div
          key={`${change.module}-${i}`}
          className="flex items-center gap-3 border-b border-slate-100 px-4 py-3"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
            <GitCommit size={13} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="truncate text-[11px] font-semibold text-slate-700">
                {change.module}
              </p>
              <span className="shrink-0 text-[10px] text-slate-400">
                {change.commit}
              </span>
            </div>
            <p className="mt-0.5 truncate text-[10px] text-slate-400">
              {change.description}
            </p>
          </div>
          <span className="hidden text-[10px] text-slate-400 sm:block">
            {change.time}
          </span>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">
            {change.changes}
          </span>
        </div>
      ))
    ) : (
      <p className="p-4 text-xs text-slate-500">
        No file-level evolution records were returned.
      </p>
    )}
  </section>
);
export default RecentCodeChanges;
