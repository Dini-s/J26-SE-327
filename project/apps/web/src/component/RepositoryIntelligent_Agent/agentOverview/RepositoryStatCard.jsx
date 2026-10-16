import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  GitCommit,
  Shield,
} from "lucide-react";

const iconMap = {
  health: Activity,
  drift: Activity,
  risk: AlertTriangle,
  shield: Shield,
  commits: GitCommit,
  size: Database,
};

const styles = {
  success: {
    icon: "bg-emerald-50 text-emerald-600",
    value: "text-slate-900",
    description: "text-emerald-600",
  },
  warning: {
    icon: "bg-violet-50 text-violet-600",
    value: "text-slate-900",
    description: "text-orange-500",
  },
  danger: {
    icon: "bg-red-50 text-red-500",
    value: "text-slate-900",
    description: "text-red-500",
  },
  info: {
    icon: "bg-blue-50 text-blue-600",
    value: "text-slate-900",
    description: "text-slate-500",
  },
};

const RepositoryStatCard = ({
  title,
  value,
  suffix,
  description,
  type = "info",
  icon,
}) => {
  const Icon = iconMap[icon] || BarChart3;
  const style = styles[type];

  return (
    <div
      className="
        group
        min-w-0
        rounded-xl
        border border-slate-200
        bg-white
        p-3
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
            flex h-10 w-10
            shrink-0
            items-center justify-center
            rounded-full
            ${style.icon}
          `}
        >
          <Icon size={19} strokeWidth={1.8} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-[12px] font-medium text-slate-500">
            {title}
          </p>

          <div className="mt-1 flex items-baseline gap-1">
            <span className={`text-xl font-bold ${style.value}`}>{value}</span>

            {suffix && (
              <span className="text-[12px] text-slate-400">{suffix}</span>
            )}
          </div>

          <p
            className={`
              mt-1
              truncate
              text-[11px]
              font-medium
              ${style.description}
            `}
          >
            {description}
          </p>
        </div>
      </div>

      {/* Small decorative chart */}
      <div className="mt-3 h-4 overflow-hidden">
        <svg
          viewBox="0 0 180 25"
          preserveAspectRatio="none"
          className="h-full w-full"
        >
          <path
            d="M0 19 L15 18 L28 20 L40 12 L52 17 L66 9 L79 17 L93 13 L106 19 L120 12 L135 17 L150 8 L164 14 L180 9"
            fill="none"
            stroke={
              type === "danger"
                ? "#F87171"
                : type === "warning"
                  ? "#A855F7"
                  : "#22C55E"
            }
            strokeWidth="1.4"
          />
        </svg>
      </div>
    </div>
  );
};

export default RepositoryStatCard;
