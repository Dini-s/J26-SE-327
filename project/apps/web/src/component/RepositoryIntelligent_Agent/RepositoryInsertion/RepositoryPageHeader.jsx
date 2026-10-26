import {
  CalendarDays,
  ChevronDown,
  Database,
  Plus,
  RefreshCw,
} from "lucide-react";

const RepositoryPageHeader = ({ onAddRepository }) => {
  return (
    <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">
          Repositories
        </h1>

        <p className="mt-1 text-xs text-slate-500">
          Manage and analyze repositories connected to ASPIRE
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Repository */}
        <button
          type="button"
          className="
            flex h-10
            items-center gap-2
            rounded-lg
            border border-slate-200
            bg-white
            px-3
            text-xs
            font-medium
            text-slate-700
            shadow-sm
            transition
            hover:border-blue-200
            hover:bg-blue-50
          "
        >
          <Database size={15} className="text-blue-600" />
          Spring PetClinic
          <ChevronDown size={13} />
        </button>

        {/* Date */}
        <div
          className="
            flex h-10
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
          <CalendarDays size={14} />
          May 12, 2025&nbsp; 09:45 AM
        </div>

        {/* Refresh */}
        <button
          type="button"
          className="
            flex h-10
            items-center gap-2
            rounded-lg
            border border-slate-200
            bg-white
            px-3
            text-xs
            font-medium
            text-slate-700
            transition
            hover:bg-slate-50
          "
        >
          <RefreshCw size={14} />
          Refresh
        </button>

        {/* Add */}
        <button
          type="button"
          onClick={onAddRepository}
          className="
            flex h-10
            items-center gap-2
            rounded-lg
            bg-blue-600
            px-4
            text-xs
            font-semibold
            text-white
            shadow-md
            shadow-blue-600/20
            transition-all
            hover:bg-blue-700
            hover:shadow-lg
          "
        >
          <Plus size={16} />
          Add Repository
        </button>
      </div>
    </div>
  );
};

export default RepositoryPageHeader;
