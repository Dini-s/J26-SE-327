
import { useState } from "react";
import {
  ChevronDown,
  Expand,
  Filter,
  Maximize2,
  Minus,
  Plus,
  Share2,
} from "lucide-react";

const ArchitectureToolbar = ({
  onZoomIn,
  onZoomOut,
  onFitView,
  onToggleFullscreen,
  onToggleLayer,
  visibleLayers = [],
  onToggleAllLayers,
  onShare,
}) => {
  const [layersOpen, setLayersOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const layers = [
    "Presentation",
    "Service",
    "Repository",
    "Infrastructure",
    "Package",
    "External",
  ];

  return (
    <div className="flex min-h-[48px] flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-white px-3 py-2">
      <div className="flex shrink-0 items-center gap-2">
        <h2 className="whitespace-nowrap text-[11px] font-bold text-slate-900">
          System Architecture Graph
        </h2>
        <span
          title="Explore package relationships and architecture metrics"
          className="cursor-help text-[9px] text-slate-400"
        >
          ⓘ
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <div className="relative">
          <button
            type="button"
            onClick={() => setLayersOpen((open) => !open)}
            aria-expanded={layersOpen}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 text-[9px] font-medium text-slate-600 hover:bg-slate-50"
          >
            Layers
            <ChevronDown size={11} />
          </button>

          {layersOpen && (
            <div className="absolute right-0 top-9 z-20 w-44 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
              <button
                type="button"
                onClick={onToggleAllLayers}
                className="mb-1 w-full rounded px-2 py-1.5 text-left text-[10px] font-medium text-indigo-600 hover:bg-slate-50"
              >
                Show all layers
              </button>

              {layers.map((layer) => (
                <label
                  key={layer}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[10px] text-slate-700 hover:bg-slate-50"
                >
                  <input
                    type="checkbox"
                    checked={
                      visibleLayers.length === 0 ||
                      visibleLayers.includes(layer)
                    }
                    onChange={() => onToggleLayer?.(layer)}
                    className="accent-indigo-600"
                  />
                  {layer}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="flex h-8 items-center rounded-md border border-slate-200 bg-white">
          <button
            type="button"
            title="Zoom out"
            onClick={onZoomOut}
            className="flex h-full w-7 items-center justify-center text-slate-500 hover:bg-slate-50"
          >
            <Minus size={11} />
          </button>

          <span className="flex h-full min-w-[38px] items-center justify-center border-x border-slate-100 text-[9px] text-slate-600">
            Zoom
          </span>

          <button
            type="button"
            title="Zoom in"
            onClick={onZoomIn}
            className="flex h-full w-7 items-center justify-center text-slate-500 hover:bg-slate-50"
          >
            <Plus size={11} />
          </button>
        </div>

        <button
          type="button"
          title="Fit graph to view"
          onClick={onFitView}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
        >
          <Expand size={13} />
        </button>

        <button
          type="button"
          title="Toggle fullscreen"
          onClick={onToggleFullscreen}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
        >
          <Maximize2 size={13} />
        </button>

        <button
          type="button"
          title="Share graph data"
          onClick={onShare}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
        >
          <Share2 size={13} />
        </button>

        <div className="relative">
          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 text-[9px] font-medium text-slate-600 hover:bg-slate-50"
          >
            <Filter size={11} />
            Filters
            <ChevronDown size={11} />
          </button>

          {filtersOpen && (
            <div className="absolute right-0 top-9 z-20 w-48 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
              <p className="text-[10px] font-semibold text-slate-800">
                Graph filters
              </p>
              <p className="mt-1 text-[10px] leading-4 text-slate-500">
                Use the Layers menu to show or hide package groups.
              </p>
              <button
                type="button"
                onClick={() => {
                  onToggleAllLayers?.();
                  setFiltersOpen(false);
                }}
                className="mt-2 w-full rounded-md bg-slate-50 px-2 py-1.5 text-[10px] font-medium text-slate-700 hover:bg-slate-100"
              >
                Reset layer visibility
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ArchitectureToolbar;
