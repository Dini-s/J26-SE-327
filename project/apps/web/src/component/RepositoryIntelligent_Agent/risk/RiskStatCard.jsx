import { Activity, AlertTriangle, Box, Shield } from "lucide-react";

const iconMap = {
  warning: AlertTriangle,
  shield: Shield,
  drift: Activity,
  critical: Shield,
  cube: Box,
};

const iconStyles = {
  red: "bg-red-50 text-red-500",
  orange: "bg-orange-50 text-orange-500",
  green: "bg-emerald-50 text-emerald-500",
  purple: "bg-purple-50 text-purple-600",
  blue: "bg-blue-50 text-blue-600",
};

const RiskStatCard = ({ title, value, description, type, icon }) => {
  const Icon = iconMap[icon] || Activity;

  return (
    <div
      className="
        group rounded-xl
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
            flex h-10 w-10 shrink-0
            items-center justify-center
            rounded-full
            ${iconStyles[type]}
          `}
        >
          <Icon size={19} />
        </div>

        <div className="min-w-0">
          <p className="truncate text-[10px] font-medium text-slate-600">
            {title}
          </p>

          <p
            className={`
              mt-1 truncate
              font-bold
              ${title === "Most Critical Module" ? "text-base" : "text-xl"}
              text-slate-900
            `}
          >
            {value}
          </p>

          <p
            className={`
              mt-1 text-[11px]
              ${
                type === "red"
                  ? "text-red-500"
                  : type === "orange"
                    ? "text-orange-500"
                    : type === "green"
                      ? "text-emerald-600"
                      : "text-slate-500"
              }
            `}
          >
            {description}
          </p>
        </div>
      </div>

      {/* Mini trend */}
      <div className="mt-3 h-5">
        <svg
          viewBox="0 0 180 25"
          preserveAspectRatio="none"
          className="h-full w-full"
        >
          <path
            d="M0 18 L12 13 L24 15 L36 7 L48 15 L60 11 L72 18 L84 12 L96 17 L108 8 L120 15 L132 10 L144 17 L156 9 L168 13 L180 7"
            fill="none"
            stroke={
              type === "red"
                ? "#EF4444"
                : type === "orange"
                  ? "#F97316"
                  : type === "green"
                    ? "#10B981"
                    : type === "purple"
                      ? "#8B5CF6"
                      : "#2563EB"
            }
            strokeWidth="1.5"
          />
        </svg>
      </div>
    </div>
  );
};

export default RiskStatCard;
