import React from "react";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { violationDistribution } from "../../../data/architectureData";

const COLORS = ["#ef4444", "#f59e0b", "#fbbf24"];

const ViolationOverview = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h2 className="text-[10px] font-bold text-slate-900">
        Violation Overview
      </h2>

      <div className="mt-3 flex items-center">
        <div className="relative h-28 w-28">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={violationDistribution}
                dataKey="value"
                innerRadius={34}
                outerRadius={50}
              >
                {violationDistribution.map((_, index) => (
                  <Cell key={index} fill={COLORS[index]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <strong className="text-lg">7</strong>

            <span className="text-[6px] text-slate-400">Total Violations</span>
          </div>
        </div>

        <div className="ml-3 space-y-3">
          {violationDistribution.map((item, index) => (
            <div key={item.name} className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  background: COLORS[index],
                }}
              />

              <span className="text-[7px] text-slate-600">{item.name}</span>

              <span className="text-[7px] font-medium">{item.value}</span>

              <span className="text-[6px] text-slate-400">
                ({item.percent})
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ViolationOverview;
