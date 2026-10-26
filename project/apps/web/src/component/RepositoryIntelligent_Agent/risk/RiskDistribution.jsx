import { useMemo } from "react";

const RISK_BANDS = [
  {
    label: "High",
    color: "#f43f5e",
    barColor: "bg-rose-500",
    dotColor: "bg-rose-500",
    textColor: "text-rose-600",
    min: 0.6,
    max: Infinity,
  },
  {
    label: "Medium",
    color: "#f59e0b",
    barColor: "bg-amber-500",
    dotColor: "bg-amber-500",
    textColor: "text-amber-600",
    min: 0.4,
    max: 0.6,
  },
  {
    label: "Low",
    color: "#10b981",
    barColor: "bg-emerald-500",
    dotColor: "bg-emerald-500",
    textColor: "text-emerald-600",
    min: -Infinity,
    max: 0.4,
  },
];

const RiskDistribution = ({ modules = [] }) => {
  const distribution = useMemo(() => {
    const available = modules.filter(
      (module) =>
        typeof module.proxyProbability === "number" &&
        Number.isFinite(module.proxyProbability)
    );

    const total = available.length;

    return RISK_BANDS.map((band) => {
      const count = available.filter(
        (module) =>
          module.proxyProbability >= band.min &&
          module.proxyProbability < band.max
      ).length;

      return {
        ...band,
        count,
        percentage: total > 0 ? (count / total) * 100 : 0,
      };
    });
  }, [modules]);

  const total = distribution.reduce(
    (sum, item) => sum + item.count,
    0
  );

  // SVG ring configuration
  const radius = 73;
  const strokeWidth = 13;
  const circumference = 2 * Math.PI * radius;

  let accumulatedCount = 0;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      {/* Header */}
      <div className="mb-5">
        <h3 className="text-base font-semibold text-slate-900">
          Package Proxy Score Bands
        </h3>

        <p className="mt-1 text-sm text-slate-500">
          Distribution of available exploratory HRIM proxy scores
        </p>
      </div>

      {/* Segmented circular progress ring */}
      <div className="mb-6 flex flex-col items-center">
        <div className="relative h-44 w-44">
          <svg
            viewBox="0 0 180 180"
            className="h-full w-full"
            role="img"
            aria-label={`Score distribution: ${distribution
              .map(
                (item) =>
                  `${item.label}: ${item.count} packages`
              )
              .join(", ")}`}
          >
            {/* Background ring */}
            <circle
              cx="90"
              cy="90"
              r={radius}
              fill="none"
              stroke="#f1f5f9"
              strokeWidth={strokeWidth}
            />

            {/* Colored segments */}
            {distribution.map((item) => {
              const segmentLength =
                total > 0
                  ? (item.count / total) * circumference
                  : 0;

              const offset =
                total > 0
                  ? (accumulatedCount / total) * circumference
                  : 0;

              accumulatedCount += item.count;

              if (item.count === 0) {
                return null;
              }

              return (
                <circle
                  key={item.label}
                  cx="90"
                  cy="90"
                  r={radius}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${segmentLength} ${
                    circumference - segmentLength
                  }`}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                  transform="rotate(-90 90 90)"
                  className="transition-all duration-500"
                />
              );
            })}
          </svg>

          {/* Center content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-bold tracking-tight text-slate-900">
              {total}
            </span>

            <span className="mt-1 text-xs font-medium text-slate-500">
              Scored packages
            </span>

            {total === 0 && (
              <span className="mt-1 text-[10px] text-slate-400">
                No scores available
              </span>
            )}
          </div>
        </div>

        <p className="mt-2 text-xs text-slate-400">
          Package score distribution
        </p>
      </div>

      {/* Distribution bars */}
      <div className="space-y-4">
        {distribution.map((item) => (
          <div key={item.label}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 shrink-0 rounded-full ${item.dotColor}`}
                />

                <span className="text-slate-600">
                  {item.label}
                </span>
              </div>

              <span className="font-medium tabular-nums text-slate-900">
                {item.count} ({item.percentage.toFixed(0)}%)
              </span>
            </div>

            <div
              className="h-2 overflow-hidden rounded-full bg-slate-100"
              role="progressbar"
              aria-label={`${item.label} proxy score band`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Number(item.percentage.toFixed(1))}
            >
              <div
                className={`h-full rounded-full transition-all duration-500 ${item.barColor}`}
                style={{
                  width: `${item.percentage}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Research disclaimer */}
      <p className="mt-5 text-xs leading-relaxed text-slate-500">
        Band thresholds are presentation categories, not validated
        model risk classifications. These values describe the
        distribution of available exploratory HRIM proxy scores.
      </p>
    </section>
  );
};

export default RiskDistribution;