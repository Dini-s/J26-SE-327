import React from "react";

const ConfidenceRing = ({ value }) => {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;

  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative h-28 w-28">
      <svg viewBox="0 0 110 110" className="-rotate-90">
        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="9"
        />

        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke="#ef4444"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700"
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-slate-900">{value}%</span>

        <span className="text-[10px] font-medium text-slate-600">
          Confidence
        </span>
      </div>
    </div>
  );
};

export default ConfidenceRing;
