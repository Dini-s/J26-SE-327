import React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { architectureIssues } from "../../../data/repositoryData";

const issueColors = ["#EF4444", "#F97316", "#F59E0B", "#8B5CF6", "#06B6D4"];

const ArchitectureIssues = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <h2 className="text-sm font-semibold text-slate-900">
            Architecture Issues
          </h2>

          <span className="text-slate-400">ⓘ</span>
        </div>

        <button className="text-[11px] text-indigo-600">View All</button>
      </div>

      <div className="flex items-center gap-3">
        {/* Donut */}
        <div className="relative h-[150px] w-[150px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={architectureIssues}
                dataKey="value"
                nameKey="name"
                innerRadius={43}
                outerRadius={62}
                paddingAngle={1}
              >
                {architectureIssues.map((_, index) => (
                  <Cell key={index} fill={issueColors[index]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <strong className="text-xl text-slate-800">17</strong>

            <span className="text-[12px] text-slate-400">Total Issues</span>
          </div>
        </div>

        {/* Legend */}
        <div className="min-w-0 flex-1 space-y-2">
          {architectureIssues.map((issue, index) => (
            <div key={issue.name} className="flex items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-sm"
                style={{
                  backgroundColor: issueColors[index],
                }}
              />

              <span className="min-w-0 flex-1 truncate text-[12px] text-slate-600">
                {issue.name}
              </span>

              <strong className="text-[11px] text-slate-700">
                {issue.value}
              </strong>

              <span className="text-[12px] text-slate-400">
                ({issue.percentage}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ArchitectureIssues;
