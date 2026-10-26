
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = [
  "#2563eb",
  "#10b981",
  "#8b5cf6",
  "#f97316",
  "#94a3b8",
];

const ArchitectureDistribution = ({ modules = [] }) => {
  const counts = modules.reduce((result, module) => {
    const layer = module.layer || "Package";
    result[layer] = (result[layer] || 0) + 1;
    return result;
  }, {});

  const distribution = Object.entries(counts).map(([name, value]) => ({
    name,
    value,
    percent: modules.length
      ? `${((value / modules.length) * 100).toFixed(1)}%`
      : "0%",
  }));

  const totalModules = modules.length;

  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h2 className="text-[12px] font-bold text-slate-900">
        Architecture Distribution
      </h2>

      <p className="mt-1 text-[10px] text-slate-500">
        Packages grouped by inferred layer
      </p>

      {totalModules === 0 ? (
        <div className="mt-4 flex min-h-28 items-center justify-center rounded-lg bg-slate-50 p-4 text-center">
          <p className="text-xs text-slate-500">
            No package data available. Run an analysis first.
          </p>
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2">
          <div className="relative h-28 w-28 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distribution}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={34}
                  outerRadius={50}
                  paddingAngle={2}
                  stroke="white"
                  strokeWidth={2}
                >
                  {distribution.map((item, index) => (
                    <Cell
                      key={item.name}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, name) => [
                    `${value} package${value === 1 ? "" : "s"}`,
                    name,
                  ]}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <strong className="text-lg text-slate-900">
                {totalModules}
              </strong>
              <span className="text-[8px] text-slate-400">Packages</span>
            </div>
          </div>

          <div className="min-w-0 flex-1 space-y-2">
            {distribution.map((item, index) => (
              <div
                key={item.name}
                className="flex min-w-0 items-center gap-1.5"
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: COLORS[index % COLORS.length] }}
                />

                <span className="min-w-0 flex-1 truncate text-[9px] text-slate-600">
                  {item.name}
                </span>

                <span className="text-[9px] font-medium text-slate-800">
                  {item.value}
                </span>

                <span className="text-[9px] text-slate-400">
                  ({item.percent})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 border-t border-slate-100 pt-2 text-[10px] leading-4 text-slate-500">
        Layer assignments are inferred from package names and are not
        verified architectural classifications.
      </p>
    </section>
  );
};

export default ArchitectureDistribution;
