const tabs = [
  "AI Explanation",
  "Recommendations",
  "Evidence & Context",
  "Metrics Impact",
  "Similar Modules",
];

const ExplanationTabs = ({
  activeTab,
  onChange,
}) => {
  return (
    <div className="flex gap-6 overflow-x-auto border-b border-slate-200">

      {tabs.map((tab) => {
        const active = activeTab === tab;

        return (
          <button
            key={tab}
            type="button"
            onClick={() => onChange(tab)}
            className={`
              relative
              whitespace-nowrap
              pb-3
              text-[11px]
              font-semibold
              transition
              ${
                active
                  ? "text-blue-600"
                  : "text-slate-500 hover:text-slate-800"
              }
            `}
          >
            {tab}

            {active && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-blue-600" />
            )}
          </button>
        );
      })}

    </div>
  );
};

export default ExplanationTabs;