
import {
  Activity,
  Code2,
  GitCommit,
  HeartPulse,
  Package,
  Users,
} from "lucide-react";

const icons = {
  health: HeartPulse,
  drift: Activity,
  module: Package,
  code: Code2,
  commit: GitCommit,
  developers: Users,
};

const styles = {
  purple: "bg-purple-50 text-purple-600",
  red: "bg-red-50 text-red-500",
  blue: "bg-blue-50 text-blue-600",
  green: "bg-emerald-50 text-emerald-600",
  orange: "bg-orange-50 text-orange-500",
};

const EvolutionStatCard = ({
  title,
  value,
  suffix,
  change,
  badge,
  type,
  icon,
}) => {
  const Icon = icons[icon];

  return (
    <div
      className="
        rounded-xl border border-slate-200
        bg-white p-3
        shadow-sm
        transition-all duration-300
        hover:-translate-y-1
        hover:shadow-md
      "
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            flex h-9 w-9 shrink-0
            items-center justify-center
            rounded-lg
            ${styles[type]}
          `}
        >
          <Icon size={18} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-medium text-slate-600">
            {title}
          </p>

          <div className="mt-1 flex items-center gap-2">
            <span className="text-xl font-bold text-slate-900">{value}</span>

            {suffix && (
              <span className="text-[10px] text-slate-500">{suffix}</span>
            )}

            {badge && (
              <span className="rounded-md bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-500">
                {badge}
              </span>
            )}
          </div>

          <p
            className={`
              mt-1 text-[10px]
              ${change?.includes("▼") ? "text-red-500" : "text-emerald-600"}
            `}
          >
            {change}
          </p>
        </div>
      </div>

      <MiniTrend type={type} />
    </div>
  );
};

const MiniTrend = ({ type }) => (
  <div className="mt-3 h-4 w-full">
    <svg
      viewBox="0 0 180 20"
      preserveAspectRatio="none"
      className="h-full w-full"
    >
      <polyline
        points="0,14 12,10 24,14 36,7 48,12 60,8 72,15 84,10 96,13 108,7 120,12 132,8 144,14 156,9 168,12 180,6"
        fill="none"
        stroke={
          type === "red"
            ? "#ef4444"
            : type === "green"
              ? "#10b981"
              : type === "orange"
                ? "#f97316"
                : "#7c3aed"
        }
        strokeWidth="1.5"
      />
    </svg>
  </div>
);

export default EvolutionStatCard;
