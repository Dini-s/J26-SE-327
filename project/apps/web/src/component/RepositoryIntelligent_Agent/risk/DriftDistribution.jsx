import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { driftDistribution } from "../../../data/riskModules";

const DriftDistribution = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">
        Drift Probability Distribution
      </h2>

      <div className="mt-3 h-36">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={driftDistribution}
            margin={{
              top: 5,
              right: 5,
              left: -25,
              bottom: 0,
            }}
          >
            <XAxis
              dataKey="range"
              tick={{
                fontSize: 8,
              }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              tick={{
                fontSize: 8,
              }}
              axisLine={false}
              tickLine={false}
            />

            <Tooltip
              contentStyle={{
                fontSize: 9,
                borderRadius: 8,
              }}
            />

            <Bar
              dataKey="value"
              fill="#6366F1"
              radius={[3, 3, 0, 0]}
              barSize={28}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
};

export default DriftDistribution;
