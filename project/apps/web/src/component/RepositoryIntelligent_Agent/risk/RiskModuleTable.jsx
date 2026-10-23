
const riskStyles = {
  HIGH: "bg-red-50 text-red-600",
  MEDIUM: "bg-orange-50 text-orange-600",
  LOW: "bg-emerald-50 text-emerald-600",
  "—": "bg-slate-100 text-slate-500",
};

const RiskModuleTable = ({ modules = [], selectedModule, onSelect }) => {
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[780px] grid-cols-[1.6fr_1.2fr_0.8fr_1fr_0.7fr_0.7fr] bg-slate-50 px-4 py-3 text-[10px] font-semibold text-slate-500">
        <span>Package</span>
        <span>Package Path</span>
        <span>Risk Band</span>
        <span>Proxy Score</span>
        <span>Fan-in</span>
        <span>Fan-out</span>
      </div>

      {modules.length === 0 ? (
        <div className="p-8 text-center text-xs text-slate-500">
          No package results available. Run repository analysis first.
        </div>
      ) : (
        modules.map((module) => (
          <button
            type="button"
            key={module.id}
            onClick={() => onSelect(module)}
            className={`grid w-full min-w-[780px] grid-cols-[1.6fr_1.2fr_0.8fr_1fr_0.7fr_0.7fr] items-center border-b border-slate-100 px-4 py-3 text-left transition ${
              selectedModule?.id === module.id
                ? "bg-blue-50/70"
                : "hover:bg-slate-50"
            }`}
          >
            <span className="pr-3 text-xs font-semibold text-slate-800">
              {module.name}
            </span>

            <span className="break-all pr-3 text-[10px] text-slate-500">
              {module.package}
            </span>

            <span
              className={`w-fit rounded-md px-2 py-1 text-[10px] font-semibold ${
                riskStyles[module.risk] || riskStyles["—"]
              }`}
            >
              {module.risk}
            </span>

            <span className="text-xs font-semibold text-slate-700">
              {module.proxyProbability == null
                ? "—"
                : `${(module.proxyProbability * 100).toFixed(2)}%`}
            </span>

            <span className="text-xs text-slate-600">
              {module.fanIn ?? "—"}
            </span>

            <span className="text-xs text-slate-600">
              {module.fanOut ?? "—"}
            </span>
          </button>
        ))
      )}
    </div>
  );
};

export default RiskModuleTable;
