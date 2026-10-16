import React from "react";
import {
  Boxes,
  Code2,
  GitBranch,
  GitCommit,
  Users,
  FileCode2,
} from "lucide-react";

import { dataSummary } from "../../../data/repositoryData";

const icons = [FileCode2, Boxes, Code2, GitBranch, Users, GitCommit];

const DataSummary = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-1">
        <h2 className="text-sm font-semibold text-slate-900">Data Summary</h2>

        <span className="text-slate-400">ⓘ</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {dataSummary.map((item, index) => {
          const Icon = icons[index];

          return (
            <div key={item.label} className="flex items-center gap-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                <Icon size={14} />
              </div>

              <div>
                <p className="text-[10px] text-slate-400">{item.label}</p>

                <p className="mt-0.5 text-xs font-bold text-slate-800">
                  {item.value}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default DataSummary;
