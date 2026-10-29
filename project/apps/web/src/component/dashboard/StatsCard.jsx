import React from "react";
import { Activity, Bot, TriangleAlert } from "lucide-react";

const icons = {
  health: Activity,
  agent: Bot,
  warning: TriangleAlert,
};

const StatCard = ({
  title,
  value,
  status,
  statusType,
  icon,
  progress,
  trend,
}) => {
  const Icon = icons[icon] || Activity;

  const statusColor =
    statusType === "warning" ? "text-orange-500" : "text-emerald-500";

  return (
    <div
      className="
        group
        rounded-xl
        border border-slate-200
        bg-white
        p-5
        shadow-sm
        transition-all duration-300
        hover:-translate-y-0.5
        hover:shadow-lg
        hover:shadow-slate-200/50
      "
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          {/* Icon */}
          <div
            className="
              flex h-16 w-16
              shrink-0
              items-center justify-center
              rounded-xl
              bg-indigo-50
              text-indigo-600
            "
          >
            <Icon size={31} strokeWidth={1.7} />
          </div>

          {/* Content */}
          <div>
            <p className="text-xs font-medium text-slate-500">{title}</p>

            <p className="mt-1 text-2xl font-bold text-indigo-600">{value}</p>

            <p
              className={`
                mt-1
                text-[11px]
                font-medium
                ${statusColor}
              `}
            >
              {status}
            </p>
          </div>
        </div>

        {/* Trend */}
        {trend && (
          <div className="hidden sm:block">
            <svg width="85" height="35" viewBox="0 0 85 35" fill="none">
              <path
                d={
                  trend === "warning"
                    ? "M1 27 C12 28, 15 11, 25 17 C35 23, 37 31, 47 16 C57 1, 61 17, 70 19 C76 20, 79 8, 84 5"
                    : "M1 17 C10 17, 12 5, 22 9 C32 13, 35 29, 44 27 C54 25, 57 10, 66 14 C74 18, 77 29, 84 25"
                }
                stroke={trend === "warning" ? "#F97316" : "#6366F1"}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </div>
        )}
      </div>

      {progress !== undefined && (
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-indigo-600 transition-all duration-1000"
            style={{
              width: `${progress}%`,
            }}
          />
        </div>
      )}
    </div>
  );
};

export default StatCard;
