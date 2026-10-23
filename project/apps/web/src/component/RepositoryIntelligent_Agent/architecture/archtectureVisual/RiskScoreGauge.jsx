
const RiskScoreGauge = ({ value }) => {
  const radius = 42;
  const circumference = Math.PI * radius;

  const numericValue = Number(value);
  const validValue =
    value !== null &&
    value !== undefined &&
    Number.isFinite(numericValue);

  const score = validValue
    ? Math.min(100, Math.max(0, numericValue))
    : 0;

  const progress = circumference * (score / 100);

  return (
    <div
      className="relative h-28 w-40 shrink-0"
      role="img"
      aria-label={
        validValue
          ? `Exploratory proxy score: ${score.toFixed(1)} percent`
          : "Exploratory proxy score unavailable"
      }
    >
      <svg viewBox="0 0 120 70" className="h-full w-full">
        <path
          d="M18 58 A42 42 0 0 1 102 58"
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="10"
          strokeLinecap="round"
        />

        {validValue && (
          <path
            d="M18 58 A42 42 0 0 1 102 58"
            fill="none"
            stroke="#6366f1"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${circumference}`}
            strokeDashoffset={circumference - progress}
            className="transition-all duration-500"
          />
        )}
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
        <span className="text-2xl font-bold text-slate-900">
          {validValue ? `${score.toFixed(0)}%` : "—"}
        </span>

        <span className="text-[9px] font-medium text-indigo-600">
          Proxy Score
        </span>
      </div>
    </div>
  );
};

export default RiskScoreGauge;
