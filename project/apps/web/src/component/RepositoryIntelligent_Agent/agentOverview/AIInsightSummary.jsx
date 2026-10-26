import { AlertTriangle, Network, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
const AIInsightSummary = ({ findings = [], riskRows = [] }) => {
  const navigate = useNavigate();
  const highest = riskRows[0];
  const topFinding = findings[0];
  const items = [
    ...(highest
      ? [
          {
            icon: AlertTriangle,
            title: `${highest.name}: ${highest.risk.toLowerCase()} risk`,
            description:
              highest.probability == null
                ? "No probability available"
                : `Returned probability: ${(highest.probability <= 1 ? highest.probability * 100 : highest.probability).toFixed(1)}%`,
          },
        ]
      : []),
    ...(topFinding
      ? [
          {
            icon: Network,
            title: String(
              topFinding.finding_type ||
                topFinding.issue_type ||
                topFinding.type ||
                topFinding.category ||
                "Architecture finding",
            ),
            description: String(
              topFinding.description ||
                topFinding.message ||
                topFinding.reason ||
                "Finding returned by repository analysis",
            ),
          },
        ]
      : []),
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">
          Analysis Insights
        </h2>
        <Sparkles size={15} className="text-indigo-500" />
      </div>
      <div className="mt-3 space-y-2">
        {items.length ? (
          items.map((item, i) => {
            const Icon = item.icon;
            return (
              <div
                key={`${item.title}-${i}`}
                className="flex items-start gap-2 rounded-lg border border-slate-100 p-2.5"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                  <Icon size={14} />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-slate-700">
                    {item.title}
                  </p>
                  <p className="mt-0.5 text-[10px] leading-4 text-slate-500">
                    {item.description}
                  </p>
                </div>
              </div>
            );
          })
        ) : (
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
            No insight candidates were returned in this analysis.
          </p>
        )}
      </div>
      <button
        onClick={() =>
          navigate(
            `/repository/ai-explanation${highest ? `?module=${encodeURIComponent(highest.name)}` : ""}`,
          )
        }
        className="mt-3 w-full rounded-lg border border-indigo-100 py-2 text-[11px] font-medium text-indigo-600 transition hover:bg-indigo-50"
      >
        Open Explanation
      </button>
    </section>
  );
};
export default AIInsightSummary;
