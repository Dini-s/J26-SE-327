import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { riskDistribution } from "../../../data/riskModules";

const COLORS = ["#EF4444", "#F59E0B", "#10B981"];

const RiskDistribution = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">
        Risk Distribution
      </h2>

      <div className="mt-3 flex flex-col items-center">
        <div className="relative h-36 w-36 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={riskDistribution}
                dataKey="value"
                innerRadius={42}
                outerRadius={62}
                paddingAngle={1}
              >
                {riskDistribution.map((_, index) => (
                  <Cell key={index} fill={COLORS[index]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <strong className="text-xl text-slate-800">38</strong>

            <span className="text-[11px] text-slate-400">Total Modules</span>
          </div>
        </div>

        <div className="space-y-3 fle">
          {riskDistribution.map((item, index) => (
            <div key={item.name} className="flex items-center ">
              <span
                className="h-2 w-2 rounded-sm"
                style={{
                  background: COLORS[index],
                }}
              />

              <span className="w-15 text-[12px] text-slate-600">
                {item.name}
              </span>

              <span className="text-[12px] text-slate-500">{item.value}</span>

              <span className="text-[10px] text-slate-400">
                ({((item.value / 38) * 100).toFixed(1)}
                %)
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default RiskDistribution;
