
const tabs = [
  {
    key: "all",
    label: "All Issues",
    count: 12,
  },
  {
    key: "High",
    label: "High",
    count: 4,
  },
  {
    key: "Medium",
    label: "Medium",
    count: 5,
  },
  {
    key: "Low",
    label: "Low",
    count: 3,
  },
  {
    key: "Resolved",
    label: "Resolved",
    count: 8,
  },
];

const IssueTabs = ({ activeTab, onChange }) => {
  return (
    <div className="flex items-center gap-5 overflow-x-auto">
      {tabs.map((tab) => {
        const active = activeTab === tab.key;

        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={`
              relative
              whitespace-nowrap
              pb-3
              text-[11px]
              font-semibold
              transition
              ${
                active ? "text-blue-600" : "text-slate-500 hover:text-slate-800"
              }
            `}
          >
            {tab.key === "High" && <span className="mr-1 text-red-500">◆</span>}

            {tab.key === "Medium" && (
              <span className="mr-1 text-orange-400">◆</span>
            )}

            {tab.key === "Low" && <span className="mr-1 text-blue-500">◆</span>}

            {tab.key === "Resolved" && (
              <span className="mr-1 text-emerald-500">↑</span>
            )}

            {tab.label}

            {tab.count && <span className="ml-1">({tab.count})</span>}

            {active && (
              <span
                className="
                  absolute
                  bottom-0
                  left-0
                  right-0
                  h-0.5
                  rounded-full
                  bg-blue-600
                "
              />
            )}
          </button>
        );
      })}
    </div>
  );
};

export default IssueTabs;
