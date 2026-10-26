
import {
  Activity,
  AlertTriangle,
  RefreshCw,
  Network,
  GitBranch,
  Box,
  FileCode2,
} from "lucide-react";

const icons = {
  health: Activity,
  warning: AlertTriangle,
  refresh: RefreshCw,
  dependency: Network,
  coupling: GitBranch,
  structure: Box,
  files: FileCode2,
};

const styles = {
  green: "bg-emerald-50 text-emerald-600",
  red: "bg-red-50 text-red-600",
  purple: "bg-purple-50 text-purple-600",
  orange: "bg-orange-50 text-orange-600",
  blue: "bg-blue-50 text-blue-600",
};

const ArchitectureStatCard = ({
  title,
  value,
  suffix,
  status,
  type = "blue",
  icon = "structure",
}) => {
  const Icon = icons[icon] || Box;
  const iconStyle = styles[type] || styles.blue;

  return (
    <article className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${iconStyle}`}
        >
          <Icon size={18} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-medium text-slate-600">
            {title}
          </p>

          <div className="mt-1 flex flex-wrap items-baseline gap-1">
            <span className="text-xl font-bold text-slate-900">
              {typeof value === "number"
                ? value.toLocaleString()
                : value ?? "—"}
            </span>

            {suffix && (
              <span className="text-[11px] text-slate-500">{suffix}</span>
            )}
          </div>

          {status && (
            <p className="mt-1 text-[11px] leading-4 text-slate-500">
              {status}
            </p>
          )}
        </div>
      </div>
    </article>
  );
};

export default ArchitectureStatCard;
