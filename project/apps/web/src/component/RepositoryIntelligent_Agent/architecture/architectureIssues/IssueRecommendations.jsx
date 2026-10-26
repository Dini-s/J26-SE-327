import { Check } from "lucide-react";

const IssueRecommendations = ({ recommendations = [] }) => {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="text-[10px] font-bold text-slate-800">Recommendations</h3>

      <div className="mt-3 space-y-2">
        {recommendations.map((recommendation) => (
          <div
            key={recommendation}
            className="
                flex
                items-start
                gap-2
                rounded-md
                border
                border-slate-100
                bg-slate-50
                p-2
              "
          >
            <span
              className="
                  flex h-5 w-5
                  shrink-0
                  items-center
                  justify-center
                  rounded-md
                  bg-emerald-50
                  text-emerald-600
                "
            >
              <Check size={11} />
            </span>

            <p className="text-[10px] font-medium leading-4 text-slate-600">
              {recommendation}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default IssueRecommendations;
