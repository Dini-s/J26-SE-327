
import { Layers, Info } from "lucide-react";

const LAYER_NAMES = [
  "Presentation",
  "Service",
  "Repository",
  "Infrastructure",
  "Package",
];

const LayerSummary = ({ modules = [] }) => {
  const layerCounts = LAYER_NAMES.map((name) => ({
    name,
    modules: modules.filter((module) => module.layer === name).length,
  })).filter((layer) => layer.modules > 0);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center gap-2">
        <Layers size={15} className="text-slate-500" />
        <h2 className="text-[11px] font-bold text-slate-900">
          Layer Summary
        </h2>
      </div>

      <p className="mt-1 text-[10px] leading-4 text-slate-500">
        Package counts grouped by inferred layer.
      </p>

      {layerCounts.length === 0 ? (
        <div className="mt-4 rounded-lg bg-slate-50 p-4">
          <p className="text-xs text-slate-600">
            No package-layer data available. Run a repository analysis first.
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {layerCounts.map((layer) => (
            <div
              key={layer.name}
              className="flex items-center justify-between gap-2"
            >
              <span className="text-[10px] text-slate-600">
                {layer.name}
              </span>

              <span className="text-[10px] font-medium text-slate-700">
                {layer.modules} {layer.modules === 1 ? "package" : "packages"}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-start gap-2 border-t border-slate-100 pt-3">
        <Info size={13} className="mt-0.5 shrink-0 text-slate-400" />
        <p className="text-[10px] leading-4 text-slate-500">
          Layer assignments are inferred from package names. Issue counts are
          omitted because validated architecture-violation data is unavailable.
        </p>
      </div>
    </section>
  );
};

export default LayerSummary;
