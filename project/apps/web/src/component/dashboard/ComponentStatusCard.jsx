import React from "react";
import StatusBadge from "../common/StatusBadge";
import ProgressRing from "../common/ProgressRing";

const colors = {
  "01": "#16A34A",
  "02": "#2563EB",
  "03": "#7C3AED",
  "04": "#F97316",
};

const ComponentStatusCard = ({
  number,
  title,
  description,
  progress,
  status,
  statusType,
}) => {
  return (
    <div
      className="
        border-b
        border-slate-100
        p-5
        transition-colors
        hover:bg-slate-50/70
      "
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="
                flex h-6 w-6
                shrink-0
                items-center justify-center
                rounded-full
                text-[9px]
                font-bold
                text-white
              "
              style={{
                backgroundColor: colors[number],
              }}
            >
              {number}
            </span>

            <h3 className="text-xs font-semibold text-slate-800">{title}</h3>
          </div>

          <p className="mt-2 max-w-[300px] text-[10px] leading-5 text-slate-500">
            {description}
          </p>

          <div className="mt-3">
            <StatusBadge type={statusType}>{status}</StatusBadge>
          </div>
        </div>

        <ProgressRing value={progress} color={colors[number]} />
      </div>
    </div>
  );
};

export default ComponentStatusCard;
