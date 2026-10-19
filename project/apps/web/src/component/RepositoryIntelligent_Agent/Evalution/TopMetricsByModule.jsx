import { topMetrics } from "../../../data/evolutionData";

const TopMetricsByModule = () => {
  const max = Math.max(...topMetrics.map((item) => item.value));

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4  shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold text-slate-900">
          Top Metrics by Module
        </h2>

        <select className="rounded-md border border-slate-200 px-2 py-1 text-[10px] text-slate-600 outline-none">
          <option>Cyclomatic Complexity</option>

          <option>Coupling</option>

          <option>Instability</option>
        </select>
      </div>

      <div className="mt-4 space-y-3">
        {topMetrics.map((item) => (
          <div key={item.module} className="flex items-center gap-2">
            <span className="w-4 text-[10px] text-slate-400">{item.rank}</span>

            <span className="w-24 truncate text-[10px] text-slate-600">
              {item.module}
            </span>

            <div className="h-1.5 flex-1 rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-purple-500 transition-all duration-700"
                style={{
                  width: `${(item.value / max) * 100}%`,
                }}
              />
            </div>

            <span className="w-6 text-right text-[10px] font-medium text-slate-600">
              {item.value}
            </span>
          </div>
        ))}
      </div>

      <button className="mt-5 text-[10px] font-medium text-blue-600">
        View All Metrics →
      </button>
    </section>
  );
};

export default TopMetricsByModule;
