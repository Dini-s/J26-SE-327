import React from "react";

const ProgressRing = ({
  value,
  size = 58,
  strokeWidth = 5,
  color = "#2563EB",
}) => {
  const radius = (size - strokeWidth) / 2;

  const circumference = 2 * Math.PI * radius;

  const offset = circumference - (value / 100) * circumference;

  return (
    <div
      className="relative shrink-0"
      style={{
        width: size,
        height: size,
      }}
    >
      <svg width={size} height={size} className="-rotate-90">
        {/* Background */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#E5E7EB"
          strokeWidth={strokeWidth}
        />

        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
      </svg>

      <span
        className="
          absolute inset-0
          flex items-center justify-center
          text-[11px]
          font-semibold
          text-slate-700
        "
      >
        {value}%
      </span>
    </div>
  );
};

export default ProgressRing;
