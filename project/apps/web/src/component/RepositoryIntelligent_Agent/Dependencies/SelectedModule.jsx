import { AlertCircle, GitBranch, Link2 } from "lucide-react";
import { dependencies } from "../../../data/dependenciesData";


const SelectedModule = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
            <GitBranch size={17} />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-800">OwnerService</h2>

              <span className="rounded bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-500">
                High Coupling
              </span>
            </div>

            <p className="text-[12px] text-slate-400">com.petclinic.owner</p>
          </div>
        </div>

        <button className="text-slate-400">⋮</button>
      </div>

      <div className="mt-3 flex gap-5 border-b border-slate-200">
        {["Overview", "Dependencies", "Dependents", "Metrics", "History"].map(
          (tab, index) => (
            <button
              key={tab}
              className={`pb-2 text-[12px] ${
                index === 0
                  ? "border-b-2 border-blue-600 font-semibold text-blue-600"
                  : "text-slate-500"
              }`}
            >
              {tab}
            </button>
          ),
        )}
      </div>

      <div className="mt-4">
        <h3 className="text-[12px] font-bold text-slate-700">
          Dependency Summary
        </h3>

        <div className="mt-3 space-y-2">
          {[
            ["Outgoing Dependencies", "14"],
            ["Incoming Dependencies", "9"],
            ["Afferent Coupling (Ca)", "9"],
            ["Efferent Coupling (Ce)", "14"],
            ["Instability (I)", "0.61"],
            ["Abstractness (A)", "0.20"],
            ["Distance (D)", "0.41"],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between">
              <span className="text-[12px] text-slate-500">{label}</span>

              <span className="text-[12px] font-semibold text-slate-700">
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <h3 className="text-[12px] font-bold text-slate-700">
          Top Dependencies
        </h3>

        <div className="mt-3 space-y-2">
          {dependencies.map((dependency) => (
            <div
              key={dependency.name}
              className="flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <Link2 size={9} className="text-purple-500" />

                <span className="text-[12px] text-slate-600">
                  {dependency.name}
                </span>
              </div>

              <span
                className={`text-[11px] font-semibold ${
                  dependency.strength === "Strong"
                    ? "text-red-500"
                    : dependency.strength === "Medium"
                      ? "text-orange-500"
                      : "text-emerald-600"
                }`}
              >
                {dependency.strength}
              </span>
            </div>
          ))}
        </div>

        <button className="mt-3 text-[12px] font-semibold text-blue-600">
          View All (14) →
        </button>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        <h3 className="text-[12px] font-bold text-slate-700">
          Risk Indicators
        </h3>

        {[
          ["High coupling", "14 outgoing dependencies", "High"],
          ["Circular dependency", "Part of 1 circular dependency", "High"],
          ["Instability", "Instability value is 0.61", "Medium"],
          ["Changes frequently", "Modified in 23 commits", "Medium"],
        ].map(([title, description, level]) => (
          <div key={title} className="mt-3 flex items-center gap-2">
            <AlertCircle
              size={12}
              className={level === "High" ? "text-red-500" : "text-orange-500"}
            />

            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-medium text-slate-700">{title}</p>

              <p className="text-[11px] text-slate-400">{description}</p>
            </div>

            <span
              className={`rounded px-2 py-1 text-[11px] font-semibold ${
                level === "High"
                  ? "bg-red-50 text-red-500"
                  : "bg-orange-50 text-orange-500"
              }`}
            >
              {level}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default SelectedModule;
