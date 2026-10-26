
import { ChevronDown, Search, SlidersHorizontal, X } from "lucide-react";

const RiskModuleFilters = ({
  search,
  setSearch,
  riskFilter = "ALL",
  setRiskFilter = () => {},
  sortOrder = "DEFAULT",
  setSortOrder = () => {},
}) => {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 p-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap gap-2">
        <div className="relative">
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            aria-label="Filter by risk score band"
            className="h-9 appearance-none rounded-lg border border-slate-200 bg-white py-0 pl-3 pr-8 text-xs font-medium text-slate-600 outline-none transition hover:border-blue-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:focus:ring-blue-900"
          >
            <option value="ALL">Risk Level: All</option>
            <option value="HIGH">High Score (≥60%)</option>
            <option value="MEDIUM">Medium Score (40–59.99%)</option>
            <option value="LOW">Low Score (&lt;40%)</option>
            <option value="UNSCORED">No Score</option>
          </select>
          <ChevronDown
            size={12}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
        </div>

        <div className="relative">
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            aria-label="Sort packages by proxy score"
            className="h-9 appearance-none rounded-lg border border-slate-200 bg-white py-0 pl-3 pr-8 text-xs font-medium text-slate-600 outline-none transition hover:border-blue-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:focus:ring-blue-900"
          >
            <option value="DEFAULT">Proxy Score: Default</option>
            <option value="DESC">Highest Proxy Score</option>
            <option value="ASC">Lowest Proxy Score</option>
          </select>
          <ChevronDown
            size={12}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
        </div>
      </div>

      <div className="relative w-full lg:w-64">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search packages..."
          aria-label="Search packages"
          className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-9 text-xs text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:placeholder:text-slate-500 dark:focus:ring-blue-900"
        />

        {search && (
          <button
            type="button"
            onClick={() => setSearch("")}
            aria-label="Clear search"
            className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 transition hover:text-slate-700 dark:hover:text-slate-200"
          >
            <X size={13} />
          </button>
        )}

        {!search && (
          <SlidersHorizontal
            size={13}
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
        )}
      </div>
    </div>
  );
};

export default RiskModuleFilters;
