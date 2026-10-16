import { GitCommit } from "lucide-react";
import { recentCodeChanges } from "../../../data/repositoryData";

const RecentCodeChanges = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">
          Recent Code Changes
          <span className="ml-1 font-normal text-slate-400">
            (Top Risk Modules)
          </span>
        </h2>

        <button className="text-[11px] text-indigo-600">View All</button>
      </div>

      <div>
        {recentCodeChanges.map((change) => (
          <div
            key={change.commit}
            className="
              flex items-center gap-3
              border-b border-slate-100
              px-4 py-3
            "
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
              <GitCommit size={13} />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-[11px] font-semibold text-slate-700">
                  {change.module}
                </p>

                <span className="text-[10px] text-slate-400">
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

            <span
              className={`
                rounded-md
                px-2 py-1
                text-[10px]
                font-semibold
                ${
                  change.type === "success"
                    ? "bg-emerald-50 text-emerald-600"
                    : "bg-red-50 text-red-500"
                }
              `}
            >
              {change.changes}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default RecentCodeChanges;
