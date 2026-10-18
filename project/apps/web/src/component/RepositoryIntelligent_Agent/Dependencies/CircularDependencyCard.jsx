import { AlertTriangle } from "lucide-react";
import { circularDependencies } from "../../../data/dependenciesData";

const CircularDependencyCard = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-[12px] font-bold text-slate-800">
          Circular Dependencies (5)
        </h2>

        <button className="text-[12px] font-semibold text-blue-600">
          View All →
        </button>
      </div>

      <div className="mt-3">
        {circularDependencies.map((item) => (
          <div
            key={item.path}
            className="flex items-center gap-2 border-b border-slate-100 py-2 last:border-0"
          >
            <AlertTriangle
              size={9}
              className={
                item.severity === "High"
                  ? "text-red-500"
                  : item.severity === "Medium"
                    ? "text-orange-500"
                    : "text-emerald-500"
              }
            />

            <span className="min-w-0 flex-1 truncate text-[11px] text-slate-600">
              {item.path}
            </span>

            <span className="rounded bg-slate-50 px-2 py-1 text-[11px]">
              {item.modules}
            </span>

            <span className="text-[11px] font-semibold text-red-500">
              {item.severity}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default CircularDependencyCard;
