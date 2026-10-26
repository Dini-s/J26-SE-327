import {
  Activity,
  GitBranch,
  Layers,
  Network,
  AlertTriangle,
} from "lucide-react";

const iconMap = {
  churn: Activity,
  coupling: Network,
  complexity: Layers,
  instability: GitBranch,
  issues: AlertTriangle,
};

const colorMap = {
  red: "bg-red-50 text-red-500",
  green: "bg-emerald-50 text-emerald-600",
  purple: "bg-purple-50 text-purple-600",
  orange: "bg-orange-50 text-orange-500",
  pink: "bg-pink-50 text-pink-500",
};

const RiskFactorCard = ({ factor }) => {
  const Icon = iconMap[factor.icon];

  return (
    <div className="flex items-center gap-3 border-b border-slate-100 py-3 last:border-0">
      <div
        className={`
          flex h-8 w-8 shrink-0
          items-center justify-center
          rounded-lg
          ${colorMap[factor.color]}
        `}
      >
        <Icon size={15} />
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-bold text-slate-800">{factor.title}</p>

        <p className="mt-1 text-[12px] leading-4 text-slate-500">
          {factor.description}
        </p>
      </div>

      <span className="shrink-0 rounded-md bg-red-50 px-2 py-1 text-[12px] font-semibold text-red-500">
        {factor.contribution}
      </span>
    </div>
  );
};

export default RiskFactorCard;
