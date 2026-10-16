import React from "react";
import {
  Activity,
  AlertTriangle,
  Box,
  GitBranch,
  Network,
  RefreshCw,
} from "lucide-react";

const icons = {
  health: Activity,
  warning: AlertTriangle,
  refresh: RefreshCw,
  dependency: Network,
  coupling: GitBranch,
  structure: Box,
};

const styles = {
  green: "bg-emerald-50 text-emerald-600",
  red: "bg-red-50 text-red-500",
  purple: "bg-purple-50 text-purple-600",
  orange: "bg-orange-50 text-orange-500",
  blue: "bg-blue-50 text-blue-600",
};

const ArchitectureStatCard = ({ title, value, suffix, status, type, icon }) => {
  const Icon = icons[icon];

  return (
    <div
      className="
        rounded-xl
        border border-slate-200
        bg-white
        p-3
        shadow-sm
        transition-all
        duration-300
        hover:-translate-y-1
        hover:shadow-md
      "
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            flex h-9 w-9 shrink-0
            items-center justify-center
            rounded-full
            ${styles[type]}
          `}
        >
          <Icon size={18} />
        </div>

        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium text-slate-600">
            {title}
          </p>

          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-bold text-slate-900">{value}</span>

            {suffix && (
              <span className="text-[11px] text-slate-500">{suffix}</span>
            )}
          </div>

          <p
            className={`
              mt-1 text-[11px] font-medium
              ${
                type === "red"
                  ? "text-red-500"
                  : type === "orange"
                    ? "text-orange-500"
                    : type === "green"
                      ? "text-emerald-600"
                      : "text-purple-600"
              }
            `}
          >
            {status}
          </p>
        </div>
      </div>

      <MiniChart type={type} />
    </div>
  );
};

const MiniChart = ({ type }) => (
  <div className="mt-3 h-4">
    <svg
      viewBox="0 0 180 20"
      preserveAspectRatio="none"
      className="h-full w-full"
    >
      <polyline
        points="
          0,14
          12,15
          25,11
          38,14
          50,9
          64,13
          76,10
          89,14
          101,7
          115,12
          128,9
          141,14
          155,8
          168,12
          180,7
        "
        fill="none"
        stroke={
          type === "red"
            ? "#ef4444"
            : type === "orange"
              ? "#f97316"
              : type === "green"
                ? "#10b981"
                : type === "blue"
                  ? "#2563eb"
                  : "#7c3aed"
        }
        strokeWidth="1.5"
      />
    </svg>
  </div>
);

export default ArchitectureStatCard;
