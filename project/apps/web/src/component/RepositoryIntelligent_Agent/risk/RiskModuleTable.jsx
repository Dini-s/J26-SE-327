
const riskStyles = {
  HIGH: "bg-red-50 text-red-500",
  MEDIUM: "bg-orange-50 text-orange-500",
  LOW: "bg-emerald-50 text-emerald-600",
};

const levelStyles = {
  High: "text-red-500",
  Medium: "text-orange-500",
  Low: "text-emerald-600",
};

const RiskModuleTable = ({ modules, selectedModule, onSelect }) => {
  return (
    <div className="overflow-x-auto">
      <div
        className="
          grid min-w-[900px]
          grid-cols-[1.5fr_1fr_0.8fr_0.7fr_0.8fr_0.8fr_0.7fr_0.8fr]
          bg-slate-50
          px-4 py-3
          text-[10px]
          font-semibold
          text-slate-500
        "
      >
        <span>Module</span>
        <span>Package</span>
        <span>Risk Level</span>
        <span>Drift Probability</span>
        <span>Trend (30d)</span>
        <span>Complexity</span>
        <span>Coupling</span>
        <span>Churn</span>
      </div>

      {modules.map((module) => (
        <div
          key={module.id}
          onClick={() => onSelect(module)}
          className={`
            grid min-w-[900px]
            cursor-pointer
            grid-cols-[1.5fr_1fr_0.8fr_0.7fr_0.8fr_0.8fr_0.7fr_0.8fr]
            items-center
            border-b
            border-slate-100
            px-4 py-3
            transition
            ${
              selectedModule?.id === module.id
                ? "bg-blue-50/60"
                : "hover:bg-slate-50"
            }
          `}
        >
          {/* Module */}
          <div className="flex items-center gap-2">
            <div
              className={`
                flex h-7 w-7
                items-center justify-center
                rounded-md
                ${
                  module.risk === "HIGH"
                    ? "bg-red-50 text-red-500"
                    : module.risk === "MEDIUM"
                      ? "bg-orange-50 text-orange-500"
                      : "bg-emerald-50 text-emerald-600"
                }
              `}
            >
              ◇
            </div>

            <div>
              <p className="text-[9px] font-semibold text-slate-800">
                {module.name}
              </p>

              <p className="text-[10px] text-slate-400">{module.package}</p>
            </div>
          </div>

          {/* Package */}
          <span className="text-[10px] text-slate-500">com.petclinic</span>

          {/* Risk */}
          <span
            className={`
              w-fit rounded-md
              px-2 py-1
              text-[10px]
              font-semibold
              ${riskStyles[module.risk]}
            `}
          >
            {module.risk}
          </span>

          {/* Drift */}
          <strong
            className={`
              text-[10px]
              ${
                module.drift >= 60
                  ? "text-red-500"
                  : module.drift >= 40
                    ? "text-orange-500"
                    : "text-slate-700"
              }
            `}
          >
            {module.drift}%
          </strong>

          {/* Trend */}
          <div className="h-7 w-14">
            <svg viewBox="0 0 70 30" className="h-full w-full">
              <polyline
                points={module.trend
                  .map((value, index) => `${index * 11},${30 - value * 0.25}`)
                  .join(" ")}
                fill="none"
                stroke={
                  module.risk === "HIGH"
                    ? "#EF4444"
                    : module.risk === "MEDIUM"
                      ? "#F97316"
                      : "#10B981"
                }
                strokeWidth="1.5"
              />
            </svg>
          </div>

          {/* Complexity */}
          <span className={`text-[10px] ${levelStyles[module.complexity]}`}>
            {module.complexity}
          </span>

          {/* Coupling */}
          <span className={`text-[10px] ${levelStyles[module.coupling]}`}>
            {module.coupling}
          </span>

          {/* Churn */}
          <span className={`text-[10px] ${levelStyles[module.churn]}`}>
            {module.churn}
          </span>
        </div>
      ))}
    </div>
  );
};

export default RiskModuleTable;
