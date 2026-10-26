import { ChevronRight } from "lucide-react";

const priorityStyles = {
  High: "bg-red-50 text-red-500",
  Medium: "bg-orange-50 text-orange-500",
  Low: "bg-blue-50 text-blue-600",
};

const RecommendationCard = ({ recommendation }) => {
  return (
    <div className="group flex gap-3 border-b border-slate-100 p-3 transition hover:bg-slate-50">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center text-[10px] font-bold text-slate-600">
        {recommendation.number}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-[10px] font-bold text-slate-800">
              {recommendation.title}
            </h3>

            <p className="mt-1 text-[10px] leading-4 text-slate-500">
              {recommendation.description}
            </p>
          </div>

          <span
            className={`
              shrink-0
              rounded-md
              px-2 py-1
              text-[11px]
              font-semibold
              ${priorityStyles[recommendation.priority]}
            `}
          >
            {recommendation.priority}
          </span>
        </div>

        <div className="mt-2 flex gap-1">
          {recommendation.tags.map((tag) => (
            <span
              key={tag}
              className="rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-500"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      <ChevronRight
        size={13}
        className="mt-5 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-blue-500"
      />
    </div>
  );
};

export default RecommendationCard;
