import React, { useState } from "react";
import {
  CalendarDays,
  ChevronDown,
  Database,
  Play,
  RefreshCw,
} from "lucide-react";

const ContentHeader = ({ title, subtitle }) => {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = () => {
    setRefreshing(true);

    setTimeout(() => {
      setRefreshing(false);
    }, 1000);
  };

  return (
    <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      {/* Left */}
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">
          {title}
        </h1>

        <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
      </div>

      {/* Right */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Repository */}
        <button
          type="button"
          className="
            flex h-9
            items-center gap-2
            rounded-lg
            border border-slate-200
            bg-white
            px-3
            text-[10px]
            font-medium
            text-slate-700
            shadow-sm
            transition
            hover:border-indigo-200
            hover:bg-indigo-50
          "
        >
          <Database size={14} className="text-indigo-600" />
          Spring PetClinic
          <ChevronDown size={13} />
        </button>

        {/* Date */}
        <div
          className="
            flex h-9
            items-center gap-2
            rounded-lg
            border border-slate-200
            bg-white
            px-3
            text-[10px]
            text-slate-600
            shadow-sm
          "
        >
          <CalendarDays size={14} className="text-slate-500" />
          May 12, 2025&nbsp; 09:45 AM
        </div>

        {/* Refresh */}
        <button
          type="button"
          onClick={handleRefresh}
          className="
            flex h-9
            items-center gap-2
            rounded-lg
            border border-slate-200
            bg-white
            px-3
            text-[10px]
            font-medium
            text-slate-700
            shadow-sm
            transition
            hover:border-indigo-200
            hover:text-indigo-600
          "
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          Refresh
        </button>

        {/* Analyze */}
        <button
          type="button"
          className="
            flex h-9
            items-center gap-2
            rounded-lg
            bg-indigo-600
            px-4
            text-[10px]
            font-semibold
            text-white
            shadow-sm
            shadow-indigo-600/20
            transition
            hover:bg-indigo-700
            hover:shadow-md
          "
        >
          <Play size={13} fill="currentColor" />
          Analyze Repository
        </button>
      </div>
    </div>
  );
};

export default ContentHeader;
