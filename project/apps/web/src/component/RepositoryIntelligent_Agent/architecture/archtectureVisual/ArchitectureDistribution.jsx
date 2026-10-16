import React from "react";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { layerDistribution } from "../../../data/architectureData";

const COLORS = ["#2563eb", "#10b981", "#8b5cf6", "#f97316", "#94a3b8"];

const ArchitectureDistribution = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h2 className="text-[12px] font-bold text-slate-900">
        Architecture Distribution
      </h2>

      <div className="mt-3 flex items-center">
        <div className="relative h-28 w-28">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={layerDistribution}
                dataKey="value"
                innerRadius={34}
                outerRadius={50}
              >
                {layerDistribution.map((_, index) => (
                  <Cell key={index} fill={COLORS[index]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <strong className="text-lg">98</strong>

            <span className="text-[8px] text-slate-400">Total Modules</span>
          </div>
        </div>

        <div className="ml-2 space-y-2">
          {layerDistribution.map((item, index) => (
            <div key={item.name} className="flex items-center gap-1.5">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: COLORS[index],
                }}
              />

              <span className="w-16 text-[9px] text-slate-600">
                {item.name}
              </span>

              <span className="text-[9px] font-medium">{item.value}</span>

              <span className="text-[9px] text-slate-400">
                ({item.percent})
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ArchitectureDistribution;
