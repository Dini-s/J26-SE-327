import React from "react";

const ArchitectureLegend = () => {
  return (
    <div
      className="
        absolute
        left-3 top-12 z-10
        w-30
        rounded-lg
        border
        border-slate-200
        bg-white/95
        p-3
        shadow-sm
        backdrop-blur
      "
    >
      <h3 className="text-[12px] font-bold text-slate-700">Legend</h3>

      <p className="mt-3 text-[11px] font-semibold text-slate-400">Layer</p>

      <LegendItem color="bg-blue-500">Presentation</LegendItem>

      <LegendItem color="bg-emerald-500">Service</LegendItem>

      <LegendItem color="bg-purple-500">Repository</LegendItem>

      <LegendItem color="bg-orange-500">Infrastructure</LegendItem>

      <LegendItem color="bg-slate-400">External</LegendItem>

      <p className="mt-3 text-[11px] font-semibold text-slate-400">Relation</p>

      <LegendItem>→ Dependency</LegendItem>

      <LegendItem>→ Uses</LegendItem>

      <LegendItem>→ Contains</LegendItem>

      <LegendItem>⚠ Violation</LegendItem>
    </div>
  );
};

const LegendItem = ({ color, children }) => (
  <div className="mt-2 flex items-center gap-2">
    {color ? (
      <span className={`h-2 w-2 rounded-full ${color}`} />
    ) : (
      <span className="text-[12px] text-slate-500">→</span>
    )}

    <span className="text-[10px] text-slate-600">{children}</span>
  </div>
);

export default ArchitectureLegend;
