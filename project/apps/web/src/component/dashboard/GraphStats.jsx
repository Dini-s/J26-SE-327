import React from "react";
import { Network, GitBranch, Boxes } from "lucide-react";

const stats = [
  {
    label: "Node",
    value: "25,910",
    icon: Network,
  },
  {
    label: "Relationship Type",
    value: "18",
    icon: GitBranch,
  },
  {
    label: "Entity Type",
    value: "12",
    icon: Boxes,
  },
];

const GraphStats = () => {
  return (
    <div className="space-y-3 border-l border-slate-100 p-4">
      {stats.map((item) => {
        const Icon = item.icon;

        return (
          <div
            key={item.label}
            className="
              rounded-lg
              border border-slate-100
              p-3
            "
          >
            <div className="flex items-center gap-2">
              <Icon size={16} className="text-indigo-600" />

              <span className="text-[10px] text-slate-500">{item.label}</span>
            </div>

            <p className="mt-2 text-lg font-bold text-slate-800">
              {item.value}
            </p>
          </div>
        );
      })}

      {/* Coverage */}
      <div className="rounded-lg border border-slate-100 p-3">
        <p className="text-[10px] text-slate-500">Graph Coverage</p>

        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-indigo-600"
            style={{ width: "72%" }}
          />
        </div>

        <p className="mt-1 text-right text-[10px] font-semibold text-slate-700">
          72%
        </p>
      </div>
    </div>
  );
};

export default GraphStats;
