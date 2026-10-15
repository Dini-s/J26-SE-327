import React from "react";
import {
  CheckCircle2,
  FileCheck2,
  AlertTriangle,
  GitPullRequest,
} from "lucide-react";

import SectionHeader from "./SectionHeader";
import { activities } from "../../data/dashboardData";

const icons = {
  repository: FileCheck2,
  analysis: CheckCircle2,
  issue: AlertTriangle,
  trace: GitPullRequest,
};

const RecentActivity = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <SectionHeader title="RECENT ACTIVITY" />

      <div>
        {activities.map((activity) => {
          const Icon = icons[activity.type];

          return (
            <div
              key={activity.title}
              className="
                flex items-center gap-3
                border-b border-slate-100
                px-4 py-3
              "
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Icon size={15} />
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate text-[10px] font-semibold text-slate-700">
                  {activity.title}
                </p>

                <p className="truncate text-[9px] text-slate-400">
                  {activity.description}
                </p>
              </div>

              <span className="shrink-0 text-[9px] text-slate-400">
                {activity.time}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default RecentActivity;
