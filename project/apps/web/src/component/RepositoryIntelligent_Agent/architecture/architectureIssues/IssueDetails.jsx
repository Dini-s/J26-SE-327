import React from "react";
import { AlertTriangle, ChevronRight, MoreVertical } from "lucide-react";

import ConfidenceRing from "./ConfidenceRing";
import DependencyFlow from "./DependencyFlow";
import CodeEvidence from "./CodeEvidence";
import IssueRecommendations from "./IssueRecommendations";
import IssueIcon from "./IssueIcon";

const IssueDetails = ({ issue, onResolve }) => {
  if (!issue) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-slate-200 bg-white">
        <div className="text-center">
          <AlertTriangle size={28} className="mx-auto text-slate-300" />

          <p className="mt-2 text-xs font-medium text-slate-500">
            Select an architecture issue
          </p>
        </div>
      </div>
    );
  }

  return (
    <section
      className="
        flex
        h-full
        min-h-[600px]
        flex-col
        rounded-xl
        border
        border-slate-200
        bg-white
        shadow-sm
      "
    >
      {/* Header */}
      <div className="flex items-start justify-between p-4">
        <div className="flex items-center gap-3">
          <IssueIcon type={issue.icon} severity={issue.severity} />

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">
                {issue.title}
              </h2>

              <span className="rounded-md bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-500">
                {issue.severity} Severity
              </span>
            </div>

            <p className="mt-1 text-[12px] font-medium text-slate-600">
              {issue.subtitle}
            </p>
          </div>
        </div>

        <button className="text-slate-400 hover:text-slate-700">
          <MoreVertical size={16} />
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-100 px-4">
        <div className="flex gap-5">
          {["Details", "Dependency Graph", "Evidence", "History"].map(
            (tab, index) => (
              <button
                key={tab}
                className={`
                relative
                pb-3
                text-[12px]
                font-semibold
                ${index === 0 ? "text-blue-600" : "text-slate-500"}
              `}
              >
                {tab}

                {index === 0 && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
                )}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Confidence + summary */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[120px_1fr]">
          <div className="flex items-center justify-center">
            <ConfidenceRing value={issue.confidence} />
          </div>

          <div className="rounded-lg border border-slate-200 p-3">
            <h3 className="text-[11px] font-bold text-slate-700">
              Issue Summary
            </h3>

            <p className="mt-2 text-[12px] leading-4 text-slate-600">
              {issue.summary}
            </p>

            <div className="mt-3 space-y-2 border-t border-slate-100 pt-2">
              <DetailRow label="Type" value={issue.title} />

              <DetailRow label="Layer" value={`${issue.layer} Layer`} />

              <DetailRow label="Detected" value={issue.detected} />
            </div>
          </div>
        </div>

        {/* Dependency */}
        {issue.dependency && (
          <div className="mt-3">
            <DependencyFlow dependency={issue.dependency} />
          </div>
        )}

        {/* Evidence + recommendations */}
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[1.4fr_0.8fr]">
          <CodeEvidence evidence={issue.evidence} />

          <IssueRecommendations recommendations={issue.recommendations} />
        </div>
      </div>

      {/* Footer action */}
      <div className="border-t border-red-100 bg-red-50/50 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-red-500" />

            <p className="text-[12px] font-medium text-red-600">
              Action Required: Resolve {issue.title.toLowerCase()} to improve
              maintainability and reduce risk.
            </p>
          </div>

          <button
            type="button"
            onClick={() => onResolve(issue.id)}
            className="
              shrink-0
              rounded-md
              border border-red-200
              bg-white
              px-3 py-1.5
              text-[12px]
              font-semibold
              text-red-600
              transition
              hover:bg-red-50
            "
          >
            Mark as Resolved
          </button>
        </div>
      </div>
    </section>
  );
};

const DetailRow = ({ label, value }) => (
  <div className="flex items-center justify-between gap-3">
    <span className="text-[12px] font-medium text-slate-500">{label}</span>

    <span className="text-[12px] font-semibold text-slate-700">{value}</span>
  </div>
);

export default IssueDetails;
