
import { softwareMetrics } from "../../../data/evolutionData";

const levelStyles = {
  High: "bg-red-50 text-red-500",
  Medium: "bg-orange-50 text-orange-500",
  Low: "bg-emerald-50 text-emerald-600",
};

const SoftwareMetricsSummary = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-900">
          Software Metrics Summary
        </h2>

        <button className="rounded-md bg-purple-50 px-3 py-1.5 text-[12px] font-medium text-purple-600">
          View All Metrics
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        {softwareMetrics.map((metric) => (
          <div
            key={metric.name}
            className="
              rounded-lg
              border border-slate-200
              p-3
              transition
              hover:border-purple-200
              hover:shadow-sm
            "
          >
            <div className="flex items-start justify-between gap-1">
              <p className="text-[10px] font-semibold text-slate-700">
                {metric.name}
              </p>
            </div>

            <p className="mt-1 text-[9px] text-slate-400">{metric.subtitle}</p>

            <div className="mt-1 flex items-center justify-between">
              <span className="text-lg font-bold text-slate-800">
                {metric.value}
              </span>

              <span
                className={`
                  rounded-md
                  px-2 py-1
                  text-[9px]
                  font-semibold
                  ${levelStyles[metric.level]}
                `}
              >
                {metric.level}
              </span>
            </div>

            <p
              className={`
                mt-1 text-[9px]
                ${
                  metric.change.includes("▼")
                    ? "text-emerald-600"
                    : "text-emerald-600"
                }
              `}
            >
              {metric.change}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default SoftwareMetricsSummary;
