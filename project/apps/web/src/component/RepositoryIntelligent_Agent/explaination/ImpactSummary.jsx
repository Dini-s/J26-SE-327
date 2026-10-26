import { GitCommit, Network, Pencil, TrendingUp } from "lucide-react";

const icons = {
  modules: Network,
  commit: GitCommit,
  edit: Pencil,
  trend: TrendingUp,
};

const ImpactSummary = ({ items }) => {
  return (
    <Card title="Impact Summary">
      <div className="space-y-3">
        {items.map((item) => {
          const Icon = icons[item.icon];

          return (
            <div key={item.label} className="flex items-center gap-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <Icon size={13} />
              </div>

              <div>
                <p className="text-[10px] text-slate-500">{item.label}</p>

                <p
                  className={`text-[11px] font-bold ${
                    item.label === "Risk Trend"
                      ? "text-red-500"
                      : "text-slate-800"
                  }`}
                >
                  {item.value}
                </p>

                {item.description && (
                  <p className="text-[9px] text-slate-400">
                    {item.description}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

export const Card = ({ title, children, action }) => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[10px] font-bold text-slate-800">{title}</h3>

        {action && (
          <button className="text-[10px] font-medium text-blue-600">
            {action}
          </button>
        )}
      </div>

      {children}
    </section>
  );
};

export default ImpactSummary;
