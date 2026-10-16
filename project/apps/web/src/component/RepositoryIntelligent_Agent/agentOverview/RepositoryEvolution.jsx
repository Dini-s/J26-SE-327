import {
  Activity,
  GitCommit,
  GitPullRequest,
  FileCode2,
  TrendingUp,
} from "lucide-react";
import { evolutionData } from "../../../data/repositoryData";

const icons = [Activity, GitCommit, FileCode2, TrendingUp, GitPullRequest];

const RepositoryEvolution = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">
          Repository Evolution Overview
        </h2>

        <button className="text-[11px] font-medium text-indigo-600">
          View Details
        </button>
      </div>

      <div className="space-y-3">
        {evolutionData.map((item, index) => {
          const Icon = icons[index];

          return (
            <div key={item.label} className="flex items-center gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                <Icon size={14} />
              </div>

              <div className="w-28 shrink-0">
                <p className="text-[11px] font-semibold text-slate-700">
                  {item.label}
                </p>

                <p className="text-[12px] text-slate-400">{item.period}</p>
              </div>

              <strong className="w-12 text-right text-xs text-slate-800">
                {item.value}
              </strong>

              <div className="min-w-0 flex-1">
                <svg
                  viewBox="0 0 180 25"
                  preserveAspectRatio="none"
                  className="h-5 w-full"
                >
                  <path
                    d="M0 17 L12 16 L24 20 L36 10 L48 18 L60 13 L72 17 L84 8 L96 15 L108 11 L120 17 L132 7 L144 13 L156 9 L168 15 L180 6"
                    fill="none"
                    stroke="#4F46E5"
                    strokeWidth="1.5"
                  />
                </svg>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default RepositoryEvolution;
