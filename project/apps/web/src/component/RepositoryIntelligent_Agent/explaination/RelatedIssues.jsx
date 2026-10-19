import { AlertTriangle } from "lucide-react";
import { Card } from "./ImpactSummary";

const RelatedIssues = ({ issues }) => {
  return (
    <Card title="Related Architecture Issues" action="View All (2)">
      <div className="space-y-3">
        {issues.map((issue) => (
          <div key={issue.title} className="flex items-center gap-2">
            <AlertTriangle size={12} className="text-red-500" />

            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold text-slate-700">
                {issue.title}
              </p>

              <p className="text-[9px] text-slate-500">{issue.description}</p>
            </div>

            <span className="rounded bg-red-50 px-2 py-1 text-[9px] font-semibold text-red-500">
              {issue.severity}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
};

export default RelatedIssues;
