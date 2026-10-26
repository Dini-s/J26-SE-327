
import { useMemo } from "react";

const DriftDistribution = ({ modules = [] }) => {
  const buckets = useMemo(() => {
    const scores = modules
      .map((module) => module.proxyProbability)
      .filter(
        (value) =>
          typeof value === "number" &&
          Number.isFinite(value) &&
          value >= 0 &&
          value <= 1
      )
      .map((value) => value * 100);

    const ranges = [
      { label: "0–20%", min: 0, max: 20 },
      { label: "20–40%", min: 20, max: 40 },
      { label: "40–60%", min: 40, max: 60 },
      { label: "60–80%", min: 60, max: 80 },
      { label: "80–100%", min: 80, max: 100 },
    ];

    return ranges.map((range) => ({
      ...range,
      count: scores.filter(
        (score) =>
          score >= range.min &&
          (range.max === 100 ? score <= 100 : score < range.max)
      ).length,
    }));
  }, [modules]);

  const maxCount = Math.max(1, ...buckets.map((bucket) => bucket.count));

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-6">
        <h3 className="text-base font-semibold text-slate-900">
          Proxy Score Distribution
        </h3>

        <p className="mt-1 text-sm text-slate-500">
          Number of packages within each score range
        </p>
      </div>

      <div className="flex h-48 items-end justify-between gap-3">
        {buckets.map((bucket) => (
          <div
            key={bucket.label}
            className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-2"
          >
            <span className="text-xs font-medium text-slate-600">
              {bucket.count}
            </span>

            <div className="flex h-36 w-full items-end overflow-hidden rounded-t-md bg-slate-100">
              <div
                className="w-full rounded-t-md bg-indigo-500 transition-all duration-300"
                style={{
                  height: `${(bucket.count / maxCount) * 100}%`,
                }}
              />
            </div>

            <span className="text-center text-[11px] text-slate-500">
              {bucket.label}
            </span>
          </div>
        ))}
      </div>

      <p className="mt-4 text-xs leading-relaxed text-slate-500">
        Scores are exploratory architecture-change proxy outputs, not validated
        drift probabilities.
      </p>
    </section>
  );
};

export default DriftDistribution;
