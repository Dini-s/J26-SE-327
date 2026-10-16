import React from "react";

import { layerSummary } from "../../../data/architectureData";

const LayerSummary = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h2 className="text-[11px] font-bold text-slate-900">Layer Summary</h2>

      <div className="mt-3 space-y-3">
        {layerSummary.map((layer) => (
          <div key={layer.name} className="flex items-center justify-between">
            <span className="text-[9px] text-slate-600">{layer.name}</span>

            <span className="text-[9px] text-slate-500">
              {layer.modules} Modules
            </span>

            <span
              className={`
                  text-[9px]
                  ${layer.issues > 0 ? "text-red-500" : "text-slate-400"}
                `}
            >
              {layer.issues} Issues
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default LayerSummary;
