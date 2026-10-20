import { ChevronDown, Search, SlidersHorizontal } from "lucide-react";

const RiskModuleFilters = ({ search, setSearch }) => {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 p-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap gap-2">
        <FilterButton>Risk Level: All</FilterButton>

        <FilterButton>Drift Probability</FilterButton>

        <FilterButton>Package: All</FilterButton>

        <FilterButton>More Filters</FilterButton>
      </div>

      <div className="relative w-full lg:w-56">
        <Search
          size={14}
          className="
            absolute left-3 top-1/2
            -translate-y-1/2
            text-slate-400
          "
        />

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search modules..."
          className="
            h-9 w-full
            rounded-lg
            border border-slate-200
            pl-9 pr-9
            text-[10px]
            outline-none
            transition
            focus:border-blue-400
            focus:ring-2
            focus:ring-blue-100
          "
        />

        <SlidersHorizontal
          size={13}
          className="
            absolute right-3 top-1/2
            -translate-y-1/2
            text-slate-400
          "
        />
      </div>
    </div>
  );
};

const FilterButton = ({ children }) => (
  <button
    type="button"
    className="
      flex h-9
      items-center gap-2
      rounded-lg
      border border-slate-200
      bg-white
      px-3
      text-[9px]
      font-medium
      text-slate-600
      transition
      hover:border-blue-200
      hover:bg-blue-50
    "
  >
    {children}

    <ChevronDown size={12} className="text-slate-400" />
  </button>
);

export default RiskModuleFilters;
