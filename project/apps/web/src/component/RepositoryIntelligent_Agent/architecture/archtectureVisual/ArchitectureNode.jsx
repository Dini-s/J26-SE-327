
import {
  Box,
  Database,
  Globe,
  Layers,
  Network,
} from "lucide-react";
import { Handle, Position } from "@xyflow/react";

const layerStyles = {
  Presentation: {
    bg: "bg-blue-50",
    border: "border-blue-300",
    icon: "text-blue-600",
  },
  Service: {
    bg: "bg-emerald-50",
    border: "border-emerald-300",
    icon: "text-emerald-600",
  },
  Repository: {
    bg: "bg-purple-50",
    border: "border-purple-300",
    icon: "text-purple-600",
  },
  Infrastructure: {
    bg: "bg-orange-50",
    border: "border-orange-300",
    icon: "text-orange-600",
  },
  External: {
    bg: "bg-slate-50",
    border: "border-slate-300",
    icon: "text-slate-600",
  },
  Package: {
    bg: "bg-slate-50",
    border: "border-slate-300",
    icon: "text-slate-600",
  },
};

const ArchitectureNode = ({ data = {} }) => {
  const layer = data.layer || "Package";
  const style = layerStyles[layer] || layerStyles.Package;

  const Icon =
    layer === "External"
      ? Database
      : layer === "Infrastructure"
        ? Box
        : layer === "Presentation"
          ? Globe
          : layer === "Service"
            ? Network
            : Layers;

  const hasProxyScore =
    data.proxyProbability !== null &&
    data.proxyProbability !== undefined &&
    Number.isFinite(Number(data.proxyProbability));

  const proxyPercentage = hasProxyScore
    ? `${(Number(data.proxyProbability) * 100).toFixed(1)}%`
    : null;

  return (
    <div
      className={`
        relative min-w-[155px] max-w-[205px]
        rounded-lg border ${style.border} ${style.bg}
        px-3 py-2 shadow-sm transition-all duration-200
        hover:-translate-y-0.5 hover:shadow-md
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />

      <div className="flex items-center gap-2">
        <div
          className={`
            flex h-7 w-7 shrink-0 items-center justify-center
            rounded-md bg-white ${style.icon}
          `}
        >
          <Icon size={14} />
        </div>

        <div className="min-w-0 flex-1">
          <p
            title={data.name || "Unnamed package"}
            className="truncate text-[12px] font-semibold text-slate-800"
          >
            {data.name || "Unnamed package"}
          </p>

          <p
            title={data.package || ""}
            className="truncate text-[9px] text-slate-500"
          >
            {data.package || "Package path unavailable"}
          </p>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="rounded bg-white/80 px-1.5 py-0.5 text-[9px] font-medium text-slate-600">
          {layer}
        </span>

        {hasProxyScore ? (
          <span className="text-[10px] font-semibold text-indigo-700">
            Proxy: {proxyPercentage}
          </span>
        ) : (
          <span className="text-[9px] text-slate-400">
            No proxy score
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-slate-200/80 pt-2 text-[9px] text-slate-600">
        <span>Files: {data.javaFiles ?? "—"}</span>
        <span>Coupling: {data.totalCoupling ?? "—"}</span>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />
    </div>
  );
};

export default ArchitectureNode;
