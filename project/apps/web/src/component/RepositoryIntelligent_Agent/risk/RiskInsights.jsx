
import { Lightbulb } from "lucide-react";
import { useMemo } from "react";

const RiskInsights = ({ modules = [] }) => {
  const insights = useMemo(() => {
    const scored = modules
      .filter(
        (module) =>
          typeof module.proxyProbability === "number" &&
          Number.isFinite(module.proxyProbability) &&
          module.proxyProbability >= 0 &&
          module.proxyProbability <= 1
      )
      .sort((a, b) => b.proxyProbability - a.proxyProbability);

    const positive = scored.filter(
      (module) => module.predictionLabel === 1
    );

    if (scored.length === 0) {
      return [
        "Run repository analysis to generate package-level proxy scores.",
      ];
    }

    const results = [
      `${scored.length} packages have an available exploratory proxy score.`,
    ];

    const highest = scored[0];

    if (highest) {
      results.push(
        `The highest current proxy score is ${(highest.proxyProbability * 100).toFixed(2)}% for ${highest.package}.`
      );
    }

    results.push(
      `${positive.length} of ${scored.length} scored packages have a positive proxy label.`
    );

    results.push(
      "These outputs are exploratory architecture-change proxies; they do not establish confirmed architecture drift."
    );

    return results;
  }, [modules]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-3">
        <div className="rounded-lg bg-amber-50 p-2 text-amber-600">
          <Lightbulb size={18} />
        </div>

        <div className="min-w-0">
          <h3 className="text-base font-semibold text-slate-900">
            Analysis Insights
          </h3>

          <p className="text-xs text-slate-500">
            Derived from the current repository analysis
          </p>
        </div>
      </div>

      <ul className="space-y-3">
        {insights.map((insight, index) => (
          <li
            key={index}
            className="flex gap-3 text-sm leading-relaxed text-slate-600"
          >
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
            <span>{insight}</span>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default RiskInsights;
