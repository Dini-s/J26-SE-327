import React from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { riskTrendData } from "../../../data/repositoryData";

const ArchitectureRiskTrend = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Architecture Risk Trend
          </h2>

          <p className="mt-1 text-[11px] text-slate-400">Risk Probability (%)</p>
        </div>

        <select
          className="
            rounded-lg
            border border-slate-200
            bg-white
            px-2 py-1.5
            text-[11px]
            text-slate-600
            outline-none
          "
          defaultValue="6"
        >
          <option value="6">Last 6 Months</option>
          <option value="12">Last 12 Months</option>
        </select>
      </div>

      <div className="h-[230px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={riskTrendData}
            margin={{
              top: 10,
              right: 10,
              left: -15,
              bottom: 0,
            }}
          >
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" />

            <XAxis
              dataKey="month"
              tick={{
                fontSize: 9,
                fill: "#64748B",
              }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{
                fontSize: 9,
                fill: "#64748B",
              }}
              axisLine={false}
              tickLine={false}
            />

            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #E2E8F0",
                fontSize: 10,
              }}
            />

            <Line
              type="monotone"
              dataKey="risk"
              stroke="#2563EB"
              strokeWidth={2}
              dot={{
                r: 3,
                fill: "#2563EB",
              }}
              activeDot={{
                r: 5,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex items-center justify-center gap-5 text-[11px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
          Architecture Drift Probability
        </span>

        <span className="flex items-center gap-1.5">
          <span className="w-5 border-t border-dashed border-orange-400" />
          Risk Threshold (60%)
        </span>
      </div>
    </section>
  );
};

export default ArchitectureRiskTrend;
