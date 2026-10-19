import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { churnData } from "../../../data/evolutionData";

const COLORS = ["#10b981", "#f87171", "#f59e0b"];

const CodeChurnChart = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold text-slate-900">
          Code Churn (Last 6 Months)
        </h2>
      </div>

      <div className="mt-4 flex items-center">
        <div className="relative h-36 w-36">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={churnData}
                dataKey="value"
                innerRadius={40}
                outerRadius={62}
                startAngle={220}
                endAngle={-40}
              >
                {churnData.map((_, index) => (
                  <Cell key={index} fill={COLORS[index]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[9px] text-slate-400">Total Changes</span>

            <strong className="text-lg text-slate-800">125,342</strong>

            <span className="text-[9px] text-emerald-600">▲ 8.3%</span>
          </div>
        </div>

        <div className="ml-3 space-y-3">
          {churnData.map((item, index) => (
            <div key={item.name} className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  background: COLORS[index],
                }}
              />

              <span className="text-[10px] text-slate-600">{item.name}</span>

              <span className="text-[10px] font-semibold text-slate-700">
                {item.value.toLocaleString()}
              </span>

              <span className="text-[9px] text-slate-400">
                ({item.percent}%)
              </span>
            </div>
          ))}
        </div>
      </div>

      <button className="mt-3 text-[10px] font-medium text-blue-600">
        View Code Churn Details →
      </button>
    </section>
  );
};

export default CodeChurnChart;
