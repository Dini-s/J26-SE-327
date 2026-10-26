
const RiskGauge = ({ value }) => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        Score unavailable
      </p>
    );
  }

  const score = Math.min(100, Math.max(0, value));
  const circumference = 251.2;
  const progress = circumference * (score / 100);

  const color =
    score >= 60 ? "#EF4444" : score >= 40 ? "#F59E0B" : "#10B981";

  const label =
    score >= 60 ? "High proxy score" :
    score >= 40 ? "Medium proxy score" :
    "Low proxy score";

  return (
    <div className="relative mx-auto h-36 w-64">
      <svg viewBox="0 0 200 110" className="h-full w-full">
        <path
          d="M25 95 A75 75 0 0 1 175 95"
          fill="none"
          stroke="#E2E8F0"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <path
          d="M25 95 A75 75 0 0 1 175 95"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          className="transition-all duration-700"
        />
      </svg>

      <div className="absolute inset-x-0 bottom-4 text-center">
        <p className="text-3xl font-bold text-slate-900">
          {score.toFixed(2)}%
        </p>
        <p className="mt-1 text-[11px] font-medium" style={{ color }}>
          {label}
        </p>
      </div>

      <span className="absolute bottom-1 left-2 text-[10px] text-slate-400">
        0%
      </span>
      <span className="absolute bottom-0 right-2 text-[10px] text-slate-400">
        100%
      </span>
    </div>
  );
};

export default RiskGauge;
