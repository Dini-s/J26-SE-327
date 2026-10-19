import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { architectureIssues } from "../../../data/evolutionData";
import { useNavigate } from "react-router-dom";

const COLORS = ["#ef4444", "#f59e0b", "#86efac"];

const ArchitectureIssuesImpact = () => {
  const navigate = useNavigate();

  const moveIssue = () => {
    navigate("/repository/issues");
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-xs font-bold text-slate-900">
        Architecture Issues Impact
      </h2>

      <div className="mt-4 flex items-center">
        <div className="relative h-32 w-32">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={architectureIssues}
                dataKey="value"
                innerRadius={38}
                outerRadius={58}
              >
                {architectureIssues.map((_, index) => (
                  <Cell key={index} fill={COLORS[index]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <strong className="text-lg">32</strong>

            <span className="text-[9px] text-slate-400">Total Issues</span>
          </div>
        </div>

        <div className="space-y-3">
          {architectureIssues.map((item, index) => (
            <div key={item.name} className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  background: COLORS[index],
                }}
              />

              <span className="w-20 text-[10px] text-slate-600">
                {item.name}
              </span>

              <span className="text-[10px] text-slate-700">{item.value}</span>

              <span className="text-[9px] text-slate-400">
                ({item.percent}%)
              </span>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={moveIssue}
        className="mt-3 text-[10px] font-medium text-blue-600"
      >
        View Architecture Issues →
      </button>
    </section>
  );
};

export default ArchitectureIssuesImpact;
