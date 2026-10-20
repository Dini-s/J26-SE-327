const RiskGauge = ({ value = 89 }) => {
  const circumference = 251.2;

  const progress = circumference * (value / 100);

  return (
    <div className="relative mx-auto h-36 w-64">
      <svg viewBox="0 0 200 110" className="h-full w-full">
        {/* Background */}
        <path
          d="M25 95 A75 75 0 0 1 175 95"
          fill="none"
          stroke="#E2E8F0"
          strokeWidth="14"
          strokeLinecap="round"
        />

        {/* Progress */}
        <path
          d="M25 95 A75 75 0 0 1 175 95"
          fill="none"
          stroke="#EF4444"
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          className="transition-all duration-1000"
        />
      </svg>

      <div className="absolute inset-x-0 bottom-4 text-center">
        <p className="text-3xl font-bold text-slate-900">{value}%</p>

        <p className="mt-1 text-[11px] font-medium text-red-500">High Risk</p>
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
