import { NavLink } from "react-router-dom";

const tabs = [
  {
    label: "Overview",
    path: "/repository/evolution",
  },
  {
    label: "Evolution Analysis",
    path: "/repository/evolution/analysis",
  },
  {
    label: "Software Metrics",
    path: "/repository/evolution/metrics",
  },
  {
    label: "Code Churn",
    path: "/repository/evolution/code-churn",
  },
  {
    label: "Compare Analysis",
    path: "/repository/evolution/compare",
  },
];

const EvolutionTabs = () => {
  return (
    <div className="mb-2 border-b border-slate-200">
      <div className="flex gap-1 overflow-x-auto">
        {tabs.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.path}
            className={({ isActive }) => `
              relative
              whitespace-nowrap
              px-5 py-3
              text-[9px]
              font-medium
              transition
              ${
                isActive
                  ? "text-blue-600"
                  : "text-slate-500 hover:text-slate-800"
              }
            `}
          >
            {tab.label}

            {location.pathname === tab.path && (
              <span
                className="
                  absolute
                  bottom-0
                  left-1/2
                  h-0.5
                  w-16
                  -translate-x-1/2
                  rounded-full
                  bg-blue-600
                "
              />
            )}
          </NavLink>
        ))}
      </div>
    </div>
  );
};

export default EvolutionTabs;
