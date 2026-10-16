import { AlertTriangle, HeartPulse, ShieldAlert } from "lucide-react";

const icons = {
  total: AlertTriangle,
  high: ShieldAlert,
  health: HeartPulse,
};

const colors = {
  total: "bg-red-50 text-red-500",
  high: "bg-red-50 text-red-500",
  health: "bg-emerald-50 text-emerald-600",
};

const IssueSummaryCard = ({ type, title, value, subtitle, change }) => {
  const Icon = icons[type];

  return (
    <div
      className="
        min-w-[150px]
        rounded-xl
        border border-slate-200
        bg-white
        px-4 py-3
        shadow-sm
        transition-all
        duration-300
        hover:-translate-y-0.5
        hover:shadow-md
      "
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            flex h-9 w-9 shrink-0
            items-center justify-center
            rounded-lg
            ${colors[type]}
          `}
        >
          <Icon size={17} />
        </div>

        <div>
          <p className="text-[10px] font-medium text-slate-500">{title}</p>

          <p className="mt-0.5 text-xl font-bold text-slate-900">{value}</p>

          <p className="text-[10px] font-medium text-slate-500">{subtitle}</p>

          {change && (
            <p className="mt-0.5 text-[10px] font-semibold text-red-500">
              {change}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default IssueSummaryCard;
