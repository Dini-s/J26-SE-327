import { Grid2X2, List, Search, SlidersHorizontal } from "lucide-react";

const RepositoryFilters = ({ search, setSearch }) => {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 p-3 sm:flex-row sm:items-center sm:justify-between">
      {/* Search */}
      <div className="relative w-full sm:max-w-[225px]">
        <Search
          size={15}
          className="
            absolute
            left-3
            top-1/2
            -translate-y-1/2
            text-slate-400
          "
        />

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search repositories..."
          className="
            h-9
            w-full
            rounded-lg
            border
            border-slate-200
            bg-white
            pl-9
            pr-3
            text-[10px]
            text-slate-700
            outline-none
            transition
            placeholder:text-slate-400
            focus:border-blue-400
            focus:ring-2
            focus:ring-blue-100
          "
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterButton>All Status</FilterButton>

        <FilterButton>All Providers</FilterButton>

        <FilterButton>Last Updated</FilterButton>

        <div className="flex overflow-hidden rounded-lg border border-slate-200">
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center bg-blue-50 text-blue-600"
            aria-label="Grid view"
          >
            <Grid2X2 size={15} />
          </button>

          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center text-slate-400 transition hover:bg-slate-50"
            aria-label="List view"
          >
            <List size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};

const FilterButton = ({ children }) => {
  return (
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
        text-slate-600
        transition
        hover:border-blue-200
        hover:bg-blue-50
      "
    >
      {children}

      <SlidersHorizontal size={11} className="rotate-90 text-slate-400" />
    </button>
  );
};

export default RepositoryFilters;
