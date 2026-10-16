import React from "react";
import { CalendarDays, ChevronRight } from "lucide-react";

import IssueIcon from "./IssueIcon";

const severityStyles = {
  High: "bg-red-50 text-red-500",
  Medium: "bg-orange-50 text-orange-500",
  Low: "bg-emerald-50 text-emerald-600",
};

const IssueCard = ({ issue, selected, onClick }) => {
  return (
    <button
      type="button"
      onClick={() => onClick(issue)}
      className={`
        group
        w-full
        rounded-lg
        border
        p-3
        text-left
        transition-all
        duration-200
        ${
          selected
            ? "border-blue-200 bg-blue-50/60 shadow-sm"
            : "border-slate-200 bg-white hover:border-blue-200 hover:shadow-sm"
        }
      `}
    >
      <div className="flex items-start gap-3">
        <IssueIcon type={issue.icon} severity={issue.severity} />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span
                  className={`
                    rounded-md
                    px-2 py-1
                    text-[11px]
                    font-semibold
                    ${severityStyles[issue.severity]}
                  `}
                >
                  {issue.severity}
                </span>

                <h3 className="text-[12px] font-bold text-slate-800">
                  {issue.title}
                </h3>
              </div>

              <p className="mt-1 text-[12px] font-medium text-slate-600">
                {issue.subtitle}
              </p>
            </div>

            <span className="rounded-md bg-red-50 px-2 py-1 text-[11px] font-medium text-red-500">
              ● {issue.status}
            </span>
          </div>

          <p className="mt-2 text-[12px] leading-4 text-slate-500">
            {issue.description}
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-purple-50 px-2 py-1 text-[11px] font-medium text-purple-600">
              {issue.type}
            </span>

            <span className="rounded-md bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-600">
              Layer: {issue.layer}
            </span>
          </div>

          <div className="mt-2 flex items-center justify-between">
            <span className="flex items-center gap-1 text-[11px] text-slate-400">
              <CalendarDays size={9} />
              {issue.date}
            </span>

            <span className="text-[11px] text-slate-500">
              Confidence <strong>{issue.confidence}%</strong>
            </span>
          </div>
        </div>

        <ChevronRight
          size={14}
          className="
            mt-6
            shrink-0
            text-slate-300
            transition
            group-hover:translate-x-0.5
            group-hover:text-blue-500
          "
        />
      </div>
    </button>
  );
};

export default IssueCard;
