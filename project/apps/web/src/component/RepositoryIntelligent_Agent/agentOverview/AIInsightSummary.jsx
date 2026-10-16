import { AlertTriangle, Network, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { aiInsights } from "../../../data/repositoryData";

const iconMap = {
  blue: Network,
  purple: Sparkles,
  orange: AlertTriangle,
};

const AIInsightSummary = () => {
  const navigate = useNavigate();

  const moveExplanation = () => {
    navigate(`/repository/ai-explanation?module=PaymentService`);
  };
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <h2 className="text-sm font-semibold text-slate-900">
            AI Insight Summary
          </h2>

          <span className="text-slate-400">ⓘ</span>
        </div>

        <button className="text-[11px] font-medium text-indigo-600">
          New (3)
        </button>
      </div>

      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/70 p-3">
        <h3 className="text-sm font-semibold text-slate-800">
          PaymentService shows high architecture-drift risk.
        </h3>

        <p className="mt-1 text-[11px] leading-4 text-slate-500">
          High code churn, elevated complexity, strong coupling and layer
          violation are the main contributing factors.
        </p>
      </div>

      <div className="mt-2 space-y-2">
        {aiInsights.map((item) => {
          const Icon = iconMap[item.type];

          return (
            <div
              key={item.title}
              className="
                flex items-center gap-2
                rounded-lg
                border border-slate-100
                p-2.5
              "
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                <Icon size={14} />
              </div>

              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-slate-700">
                  {item.title}
                </p>

                <p className="mt-0.5 text-[10px] text-slate-400">
                  {item.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={moveExplanation}
        className="
          mt-3
          w-full
          rounded-lg
          border border-indigo-100
          py-2
          text-[11px]
          font-medium
          text-indigo-600
          transition
          hover:bg-indigo-50
        "
      >
        Explain in Detail
      </button>
    </section>
  );
};

export default AIInsightSummary;
