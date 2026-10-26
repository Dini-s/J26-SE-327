
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { evolutionTrend } from "../../../data/evolutionData";

const EvolutionTrend = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xs font-bold text-slate-900">
            Evolution Trend (Over Time)
          </h2>
        </div>
      </div>

      {/* Controls */}
      <div className="mt-4 flex items-center gap-4">
        <div className="flex-1">
          <label className="mb-1 block text-[9px] text-slate-400">Metric</label>

          <select className="h-8 w-full rounded-md border border-slate-200 px-2 text-[11px] text-slate-600 outline-none">
            <option>Architecture Health Score</option>
            <option>Drift Probability</option>
            <option>Maintainability Index</option>
          </select>
        </div>

        <div className="w-28">
          <label className="mb-1 block text-[9px] text-slate-400">
            Time Range
          </label>

          <select className="h-8 w-full rounded-md border border-slate-200 px-2 text-[11px] text-slate-600 outline-none">
            <option>Last 6 Months</option>
            <option>Last 12 Months</option>
          </select>
        </div>

        <div className="hidden text-right sm:block">
          <p className="text-[9px] text-slate-400">Current Score</p>

          <p className="text-xl font-bold text-purple-600">
            72
            <span className="text-[10px] text-slate-400"> / 100</span>
          </p>
        </div>
      </div>

      <div className="mt-3 h-[185px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={evolutionTrend}
            margin={{
              top: 10,
              right: 10,
              left: -25,
              bottom: 0,
            }}
          >
            <defs>
              <linearGradient id="healthGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.25} />

                <stop offset="100%" stopColor="#7c3aed" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke="#e2e8f0"
              vertical
              horizontal
              strokeDasharray="0"
            />

            <XAxis
              dataKey="month"
              tick={{
                fontSize: 8,
              }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{
                fontSize: 8,
              }}
              axisLine={false}
              tickLine={false}
            />

            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #e2e8f0",
                fontSize: 9,
              }}
            />

            <Line
              type="monotone"
              dataKey="score"
              stroke="#6d28d9"
              strokeWidth={2}
              dot={{
                r: 3,
                fill: "#6d28d9",
              }}
              activeDot={{
                r: 5,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
        <span className="h-2 w-2 rounded-full bg-purple-600" />
        Architecture Health Score
      </div>
    </section>
  );
};

export default EvolutionTrend;
