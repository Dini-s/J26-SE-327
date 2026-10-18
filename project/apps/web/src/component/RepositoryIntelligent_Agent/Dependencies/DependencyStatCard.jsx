import {
  Activity,
  Box,
  CircleAlert,
  GitBranch,
  HeartPulse,
  Link2,
} from "lucide-react";

const icons = {
  link: Link2,
  cube: Box,
  coupling: GitBranch,
  refresh: Activity,
  health: HeartPulse,
  orphan: CircleAlert,
};

const colors = {
  blue: "bg-blue-50 text-blue-600",
  orange: "bg-orange-50 text-orange-500",
  red: "bg-red-50 text-red-500",
  green: "bg-emerald-50 text-emerald-600",
  purple: "bg-purple-50 text-purple-600",
};

const DependencyStatCard = ({ stat }) => {
  const Icon = icons[stat.icon];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${colors[stat.color]}`}
        >
          <Icon size={19} />
        </div>

        <div className="min-w-0">
          <p className="text-[12px] font-medium text-slate-600">{stat.title}</p>

          <div className="mt-1 flex items-center gap-2">
            {stat.health ? (
              <div className="h-10 w-10 rounded-full border-[6px] border-emerald-500 border-r-slate-200 flex items-center justify-center">
                <span className="text-[11px] font-bold text-slate-800">
                  {stat.value}
                </span>
              </div>
            ) : (
              <p className="text-xl font-bold text-slate-900">{stat.value}</p>
            )}
          </div>

          <p
            className={`mt-1 text-[12px] ${
              stat.trend === "up"
                ? "text-emerald-600"
                : stat.trend === "down"
                  ? "text-emerald-600"
                  : "text-slate-400"
            }`}
          >
            {stat.subtitle}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-end gap-1">
        {[30, 42, 35, 48, 38, 45, 35, 50, 40, 46, 37, 52].map(
          (height, index) => (
            <div
              key={index}
              className={`w-full rounded-full ${
                stat.color === "red"
                  ? "bg-red-300"
                  : stat.color === "orange"
                    ? "bg-orange-300"
                    : "bg-blue-300"
              }`}
              style={{ height: `${height / 3}px` }}
            />
          ),
        )}
      </div>
    </div>
  );
};

export default DependencyStatCard;
