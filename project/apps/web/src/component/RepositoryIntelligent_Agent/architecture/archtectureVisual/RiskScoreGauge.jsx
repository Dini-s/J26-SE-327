import React from "react";

const RiskScoreGauge = ({ value }) => {
  const radius = 42;
  const circumference = Math.PI * radius;

  const progress = circumference * (value / 100);

  return (
    <div className="relative h-28 w-40">
      <svg viewBox="0 0 120 70" className="h-full w-full">
        <path
          d="M18 58 A42 42 0 0 1 102 58"
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="10"
          strokeLinecap="round"
        />

        <path
          d="M18 58 A42 42 0 0 1 102 58"
          fill="none"
          stroke="#ef4444"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          className="transition-all duration-1000"
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
        <span className="text-2xl font-bold text-slate-900">{value}%</span>

        <span className="text-[9px] font-medium text-red-500">High Risk</span>
      </div>
    </div>
  );
};

export default RiskScoreGauge;
