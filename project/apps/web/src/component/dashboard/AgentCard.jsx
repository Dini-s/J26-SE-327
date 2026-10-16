import React from "react";
import { Layers3 } from "lucide-react";

const AgentCard = ({ name, component }) => {
  return (
    <div
      className="
        flex items-center gap-3
        border-b border-slate-100
        p-5
        transition
        hover:bg-slate-50
      "
    >
      <div
        className="
          flex h-12 w-12
          shrink-0
          items-center justify-center
          rounded-xl
          bg-indigo-50
          text-indigo-600
        "
      >
        <Layers3 size={25} strokeWidth={1.7} />
      </div>

      <div className="min-w-0">
        <h3 className="text-xs font-semibold text-slate-800">{name}</h3>

        <p className="mt-1 truncate text-[10px] text-slate-500">{component}</p>

        <div className="mt-1.5 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />

          <span className="text-[10px] font-medium text-emerald-600">
            Active
          </span>
        </div>
      </div>
    </div>
  );
};

export default AgentCard;
