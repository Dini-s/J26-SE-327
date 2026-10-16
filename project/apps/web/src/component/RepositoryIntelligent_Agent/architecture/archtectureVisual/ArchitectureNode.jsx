import React from "react";
import { Box, Database, Globe, Layers } from "lucide-react";
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
};

const riskStyles = {
  High: "text-red-500",
  Medium: "text-orange-500",
  Low: "text-emerald-600",
};

const ArchitectureNode = ({ data }) => {
  const style = layerStyles[data.layer];

  const Icon =
    data.layer === "External"
      ? Database
      : data.layer === "Infrastructure"
        ? Box
        : data.layer === "Presentation"
          ? Globe
          : Layers;

  return (
    <div
      className={`
        relative
        min-w-[145px]
        rounded-lg
        border
        ${style.border}
        ${style.bg}
        px-3 py-2
        shadow-sm
        transition-all
        duration-200
        hover:-translate-y-0.5
        hover:shadow-md
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
            flex h-7 w-7
            items-center justify-center
            rounded-md bg-white
            ${style.icon}
          `}
        >
          <Icon size={14} />
        </div>

        <div className="min-w-0">
          <p className="truncate text-[12px] font-semibold text-slate-800">
            {data.name}
          </p>

          <p className="truncate text-[9px] text-slate-400">{data.package}</p>
        </div>
      </div>

      <p
        className={`
          mt-2
          text-[9px]
          font-medium
          ${riskStyles[data.risk]}
        `}
      >
        Risk: {data.risk}
      </p>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />
    </div>
  );
};

export default ArchitectureNode;
