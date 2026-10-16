import React from "react";
import {
  ChevronDown,
  Expand,
  Filter,
  Maximize2,
  Minus,
  Plus,
  Share2,
} from "lucide-react";

const ArchitectureToolbar = () => {
  return (
    <div className="flex min-h-[48px] items-center justify-between border-b border-slate-100 bg-white px-3">
      {/* LEFT */}
      <div className="flex items-center gap-2 shrink-0">
        <h2 className="text-[11px] font-bold text-slate-900 whitespace-nowrap">
          System Architecture Graph
        </h2>

        <span className="text-[9px] text-slate-400">ⓘ</span>
      </div>

      {/* RIGHT */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Layers */}
        <button
          type="button"
          className="
            inline-flex h-8
            items-center justify-center
            gap-1
            whitespace-nowrap
            rounded-md
            border border-slate-200
            bg-white
            px-2.5
            text-[9px]
            font-medium
            text-slate-600
            transition
            hover:bg-slate-50
            hover:text-slate-900
          "
        >
          <span>Layers</span>
          <ChevronDown size={11} />
        </button>

        {/* Zoom */}
        <div
          className="
            flex h-8
            items-center
            rounded-md
            border border-slate-200
            bg-white
          "
        >
          <button
            type="button"
            className="
              flex h-full w-7
              items-center justify-center
              text-slate-500
              transition
              hover:bg-slate-50
              hover:text-slate-900
            "
          >
            <Minus size={11} />
          </button>

          <span
            className="
              flex h-full min-w-[38px]
              items-center justify-center
              border-x border-slate-100
              text-[9px]
              font-medium
              text-slate-600
            "
          >
            100%
          </span>

          <button
            type="button"
            className="
              flex h-full w-7
              items-center justify-center
              text-slate-500
              transition
              hover:bg-slate-50
              hover:text-slate-900
            "
          >
            <Plus size={11} />
          </button>
        </div>

        {/* Fit */}
        <button
          type="button"
          title="Fit View"
          className="
            flex h-8 w-8
            shrink-0
            items-center justify-center
            rounded-md
            border border-slate-200
            bg-white
            text-slate-600
            transition
            hover:bg-slate-50
            hover:text-slate-900
          "
        >
          <Expand size={13} />
        </button>

        {/* Fullscreen */}
        <button
          type="button"
          title="Fullscreen"
          className="
            flex h-8 w-8
            shrink-0
            items-center justify-center
            rounded-md
            border border-slate-200
            bg-white
            text-slate-600
            transition
            hover:bg-slate-50
            hover:text-slate-900
          "
        >
          <Maximize2 size={13} />
        </button>

        {/* Share */}
        <button
          type="button"
          title="Share"
          className="
            flex h-8 w-8
            shrink-0
            items-center justify-center
            rounded-md
            border border-slate-200
            bg-white
            text-slate-600
            transition
            hover:bg-slate-50
            hover:text-slate-900
          "
        >
          <Share2 size={13} />
        </button>

        {/* Filters */}
        <button
          type="button"
          className="
            inline-flex h-8
            items-center justify-center
            gap-1
            whitespace-nowrap
            rounded-md
            border border-slate-200
            bg-white
            px-2.5
            text-[9px]
            font-medium
            text-slate-600
            transition
            hover:bg-slate-50
            hover:text-slate-900
          "
        >
          <Filter size={11} />
          <span>Filters</span>
          <ChevronDown size={11} />
        </button>
      </div>
    </div>
  );
};

export default ArchitectureToolbar;
