import React from "react";
import { ArrowRight } from "lucide-react";

const SectionHeader = ({ title, action = "View all", onAction }) => {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>

      <button
        type="button"
        onClick={onAction}
        className="group flex items-center gap-1 text-xs font-medium text-indigo-600 transition hover:text-indigo-700"
      >
        {action}

        <ArrowRight
          size={13}
          className="transition-transform group-hover:translate-x-0.5"
        />
      </button>
    </div>
  );
};

export default SectionHeader;
