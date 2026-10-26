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
  orange: "bg-orange-50 text-orange-600",
  red: "bg-rose-50 text-rose-600",
  green: "bg-emerald-50 text-emerald-600",
  purple: "bg-violet-50 text-violet-600",
};
const DependencyStatCard = ({ stat }) => {
  const Icon = icons[stat.icon] || Box;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${colors[stat.color] || colors.blue}`}
        >
          <Icon size={17} />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-600">{stat.title}</p>
          <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
            {stat.value}
          </p>
          <p className="mt-1 text-[10px] leading-4 text-slate-500">
            {stat.subtitle}
          </p>
        </div>
      </div>
    </div>
  );
};
export default DependencyStatCard;
