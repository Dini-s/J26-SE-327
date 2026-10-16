import React from "react";
import {
  AlertTriangle,
  ChevronRight,
  GitBranch,
  MoreVertical,
  ShieldAlert,
} from "lucide-react";

import RiskScoreGauge from "./RiskScoreGauge";

import { keyIssues, topDependencies } from "../../../data/architectureData";
import { useNavigate } from "react-router-dom";

const SelectedModulePanel = ({ module }) => {
  const navigate = useNavigate();

  const moveIssues = () => {
    navigate("/repository/issues");
  };
  if (!module) {
    return (
      <aside className="rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-xs text-slate-400">
          Select a module from the architecture graph.
        </p>
      </aside>
    );
  }

  return (
    <aside
      className="
        rounded-xl
        border border-slate-200
        bg-white
        p-4
        shadow-sm
      "
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-50 text-red-500">
            <ShieldAlert size={18} />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold text-slate-900">
                {module.name}
              </h2>

              <span className="rounded-md bg-red-50 px-2 py-1 text-[9px] font-semibold text-red-500">
                HIGH RISK
              </span>
            </div>

            <p className="mt-1 text-[10px] text-slate-400">{module.package}</p>
          </div>
        </div>

        <MoreVertical size={15} className="text-slate-400" />
      </div>

      {/* Tabs */}
      <div className="mt-4 flex border-b border-slate-100">
        {["Overview", "Dependencies", "Metrics", "Issues", "History"].map(
          (tab, index) => (
            <button
              key={tab}
              className={`
              relative px-2 pb-2
              text-[10px]
              ${index === 0 ? "font-semibold text-blue-600" : "text-slate-500"}
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

      {/* Score */}
      <div className="mt-4">
        <h3 className="text-[9px] font-semibold text-slate-700">Risk Score</h3>

        <div className="flex items-center">
          <RiskScoreGauge value={module.score} />

          <div className="ml-3 space-y-3">
            <InfoItem label="Rank" value={module.rank} />

            <InfoItem label="Trend (30d)" value={`↗ ${module.trend}`} danger />

            <InfoItem label="Last Analyzed" value={module.lastAnalyzed} />

            <InfoItem label="First Detected" value={module.firstDetected} />
          </div>
        </div>
      </div>

      {/* Issues */}
      <div className="mt-4 border-t border-slate-100 pt-4">
        <h3 className="text-[9px] font-semibold text-slate-700">Key Issues</h3>

        <div className="mt-3 space-y-2">
          {keyIssues.map((issue) => (
            <div key={issue.name} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle
                  size={11}
                  className={
                    issue.level === "High" ? "text-red-500" : "text-orange-500"
                  }
                />

                <span className="text-[10px] text-slate-600">{issue.name}</span>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-600">
                  {issue.count}
                </span>

                <span
                  className={`
                    text-[9px]
                    ${
                      issue.level === "High"
                        ? "text-red-500"
                        : "text-orange-500"
                    }
                  `}
                >
                  {issue.level}
                </span>
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={moveIssues}
          className="mt-3 flex items-center gap-1 text-[10px] font-medium text-blue-600"
        >
          View All Issues
          <ChevronRight size={11} />
        </button>
      </div>

      {/* Dependencies */}
      <div className="mt-4 border-t border-slate-100 pt-4">
        <div className="flex items-center justify-between">
          <h3 className="text-[9px] font-semibold text-slate-700">
            Top Dependencies
          </h3>

          <button className="text-[9px] text-blue-600">View All</button>
        </div>

        <div className="mt-3 space-y-2">
          {topDependencies.map((dependency) => (
            <div
              key={dependency.name}
              className="flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <GitBranch size={11} className="text-slate-500" />

                <span className="text-[10px] text-slate-600">
                  {dependency.name}
                </span>
              </div>

              <span
                className={`
                    text-[9px]
                    ${
                      dependency.level === "Strong"
                        ? "text-red-500"
                        : dependency.level === "Medium"
                          ? "text-orange-500"
                          : "text-emerald-600"
                    }
                  `}
              >
                {dependency.level}
              </span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
};

const InfoItem = ({ label, value, danger }) => (
  <div>
    <p className="text-[9px] text-slate-400">{label}</p>

    <p
      className={`
        mt-0.5 text-[10px] font-semibold
        ${danger ? "text-red-500" : "text-slate-700"}
      `}
    >
      {value}
    </p>
  </div>
);

export default SelectedModulePanel;
