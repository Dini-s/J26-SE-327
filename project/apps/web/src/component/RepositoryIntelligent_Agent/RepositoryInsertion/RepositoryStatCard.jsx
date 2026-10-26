import {
  Activity,
  AlertTriangle,
  Database,
  PauseCircle,
  RefreshCw,
} from "lucide-react";

const iconMap = {
  database: Database,
  refresh: RefreshCw,
  activity: Activity,
  pause: PauseCircle,
  warning: AlertTriangle,
};

const styles = {
  blue: "bg-blue-50 text-blue-600",
  purple: "bg-purple-50 text-purple-600",
  orange: "bg-orange-50 text-orange-500",
  red: "bg-red-50 text-red-500",
};

const RepositoryStatCard = ({ title, value, description, type, icon }) => {
  const Icon = iconMap[icon];

  return (
    <div
      className="
        rounded-xl
        border border-slate-200
        bg-white
        p-4
        shadow-sm
        transition-all
        duration-300
        hover:-translate-y-0.5
        hover:shadow-md
      "
    >
      <div className="flex items-center gap-3">
        <div
          className={`
            flex h-11 w-11
            shrink-0
            items-center justify-center
            rounded-xl
            ${styles[type]}
          `}
        >
          <Icon size={21} />
        </div>

        <div className="min-w-0">
          <p className="text-[10px] text-slate-500">{title}</p>

          <p className="mt-0.5 text-xl font-bold text-slate-900">{value}</p>

          <p
            className={`
              mt-0.5
              text-[11px]
              ${
                type === "red"
                  ? "text-red-500"
                  : type === "orange"
                    ? "text-orange-500"
                    : "text-slate-500"
              }
            `}
          >
            {description}
          </p>
        </div>
      </div>
    </div>
  );
};

export default RepositoryStatCard;
