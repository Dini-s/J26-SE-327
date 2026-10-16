import React from "react";
import { ChevronDown, Search } from "lucide-react";

const IssueFilters = ({
  search,
  setSearch,
  severity,
  setSeverity,
  type,
  setType,
  layer,
  setLayer,
}) => {
  return (
    <div
      className="
        flex flex-wrap
        items-center
        gap-2
      "
    >
      {/* Search */}
      <div
        className="
          flex h-8
          w-[190px]
          items-center
          gap-2
          rounded-md
          border border-slate-200
          bg-white
          px-2.5
        "
      >
        <Search size={13} className="text-slate-400" />

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search issues..."
          className="
            w-full
            bg-transparent
            text-[11px]
            text-slate-700
            outline-none
            placeholder:text-slate-400
          "
        />
      </div>

      <FilterSelect
        label={`Severity: ${severity}`}
        onChange={setSeverity}
        options={["All", "High", "Medium", "Low"]}
      />

      <FilterSelect
        label={`Type: ${type}`}
        onChange={setType}
        options={[
          "All",
          "Design Violation",
          "Architecture",
          "Code Smell",
          "Quality Risk",
          "Maintainability",
        ]}
      />

      <FilterSelect
        label={`Layer: ${layer}`}
        onChange={setLayer}
        options={[
          "All",
          "Presentation",
          "Service",
          "Repository",
          "Infrastructure",
        ]}
      />
    </div>
  );
};

const FilterSelect = ({ label, options, onChange }) => {
  return (
    <div className="relative">
      <select
        onChange={(e) => onChange(e.target.value)}
        className="
          h-8
          min-w-[105px]
          appearance-none
          rounded-md
          border border-slate-200
          bg-white
          pl-3 pr-7
          text-[11px]
          font-medium
          text-slate-600
          outline-none
          transition
          hover:border-blue-200
        "
      >
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>

      <ChevronDown
        size={11}
        className="
          pointer-events-none
          absolute
          right-2
          top-1/2
          -translate-y-1/2
          text-slate-400
        "
      />
    </div>
  );
};

export default IssueFilters;
