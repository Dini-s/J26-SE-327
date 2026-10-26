import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
const colors = [
  "#EF4444",
  "#F97316",
  "#F59E0B",
  "#8B5CF6",
  "#06B6D4",
  "#64748B",
];
const ArchitectureIssues = ({ issues = [] }) => {
  const total = issues.reduce((n, i) => n + i.value, 0);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">
          Architecture Findings
        </h2>
        <span className="text-[10px] text-slate-400">Backend results</span>
      </div>
      {issues.length ? (
        <div className="flex items-center gap-3">
          <div className="relative h-[150px] w-[150px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={issues}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={43}
                  outerRadius={62}
                  paddingAngle={1}
                >
                  {issues.map((_, i) => (
                    <Cell key={i} fill={colors[i % colors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <strong className="text-xl text-slate-800">{total}</strong>
              <span className="text-[12px] text-slate-400">Findings</span>
            </div>
          </div>
          <div className="min-w-0 flex-1 space-y-2">
            {issues.slice(0, 6).map((issue, i) => (
              <div key={issue.name} className="flex items-center gap-2">
                <span
                  className="h-2 w-2 shrink-0 rounded-sm"
                  style={{ backgroundColor: colors[i % colors.length] }}
                />
                <span className="min-w-0 flex-1 truncate text-[11px] text-slate-600">
                  {issue.name}
                </span>
                <strong className="text-[11px] text-slate-700">
                  {issue.value}
                </strong>
                <span className="text-[11px] text-slate-400">
                  ({issue.percentage}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="py-8 text-xs text-slate-500">
          No architecture findings were returned. This does not necessarily mean
          the repository has no architectural risks.
        </p>
      )}
    </section>
  );
};
export default ArchitectureIssues;
