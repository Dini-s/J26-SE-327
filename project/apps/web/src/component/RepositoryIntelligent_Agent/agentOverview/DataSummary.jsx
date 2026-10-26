
import {
  Boxes,
  Code2,
  GitBranch,
  GitCommit,
  Users,
  FileCode2,
  Info,
} from "lucide-react";

const icons = [
  FileCode2,
  Boxes,
  Code2,
  GitBranch,
  Users,
  GitCommit,
];

const DataSummary = ({ items = [] }) => (
  <section className="h-fit min-w-0 self-start rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    {/* Header */}
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold text-slate-900">
          Data Summary
        </h2>
        <Info
          size={15}
          className="text-slate-400"
          aria-label="Information about repository statistics"
        />
      </div>

      <span className="text-xs font-medium text-slate-400">
        {items.length} metrics
      </span>
    </div>

    {/* Metrics grid */}
    <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
      {items.map((item, index) => {
        const Icon = icons[index % icons.length];

        return (
          <div
            key={item.label}
            className="group flex min-w-0 items-start gap-3
              rounded-xl border border-slate-100 bg-slate-50/70
              p-3 transition-all duration-200
              hover:border-indigo-100 hover:bg-indigo-50/50"
          >
            <div
              className="flex h-9 w-9 shrink-0 items-center
                justify-center rounded-lg bg-indigo-100/80
                text-indigo-600 transition-colors
                group-hover:bg-indigo-100"
            >
              <Icon size={17} strokeWidth={1.8} />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-xs leading-5 text-slate-500">
                {item.label}
              </p>

              <p className="mt-1 break-words text-xl font-bold
                leading-tight tracking-tight text-slate-900">
                {item.value ?? "—"}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  </section>
);

export default DataSummary;
