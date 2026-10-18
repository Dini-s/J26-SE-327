const tabs = [
  "Dependency Graph",
  "Dependency Matrix",
  "Package Dependencies",
  "Layer Dependencies",
];

const DependencyTabs = ({ activeTab, onChange }) => {
  return (
    <div className="flex overflow-x-auto border-b border-slate-200">
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          className={`whitespace-nowrap px-4 py-2.5 text-[12px] font-medium transition ${
            activeTab === tab
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-slate-500 hover:text-slate-800"
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
};

export default DependencyTabs;
