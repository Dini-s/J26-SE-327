import React from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, RotateCw } from "lucide-react";

const DependencyFlow = ({ dependency }) => {
  if (!dependency) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="text-[10px] font-bold text-slate-800">Dependency Flow</h3>

      <div className="mt-4 flex items-center justify-center gap-4">
        {/* Source */}
        <div
          className="
            flex h-14
            min-w-[130px]
            flex-col
            items-center
            justify-center
            rounded-lg
            border border-purple-200
            bg-purple-50
          "
        >
          <span className="text-[10px] font-bold text-slate-800">
            {dependency.source}
          </span>

          <span className="text-[9px] text-slate-500">
            ({dependency.sourcePackage})
          </span>
        </div>

        {/* Circular */}
        <div className="flex flex-col items-center">
          <div className="flex items-center gap-1 text-red-500">
            <ArrowLeft size={18} />

            <RotateCw
              size={26}
              className="animate-spin"
              style={{
                animationDuration: "3s",
              }}
            />

            <ArrowRight size={18} />
          </div>

          <span className="mt-1 text-[10px] font-bold text-red-500">
            Circular
          </span>

          <span className="text-[10px] font-bold text-red-500">Dependency</span>
        </div>

        {/* Target */}
        <div
          className="
            flex h-14
            min-w-[130px]
            flex-col
            items-center
            justify-center
            rounded-lg
            border border-purple-200
            bg-purple-50
          "
        >
          <span className="text-[10px] font-bold text-slate-800">
            {dependency.target}
          </span>

          <span className="text-[9px] text-slate-500">
            ({dependency.targetPackage})
          </span>
        </div>
      </div>
    </div>
  );
};

export default DependencyFlow;
