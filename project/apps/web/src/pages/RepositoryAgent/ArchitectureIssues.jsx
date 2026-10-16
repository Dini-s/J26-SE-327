import { useMemo, useState } from "react";
import { issues, issueSummary } from "../../data/architectureIssuesData";
import { AlertTriangle } from "lucide-react";
import IssueSummaryCard from "../../component/RepositoryIntelligent_Agent/architecture/architectureIssues/IssueSummaryCard";
import IssueTabs from "../../component/RepositoryIntelligent_Agent/architecture/architectureIssues/IssueTabs";
import IssueFilters from "../../component/RepositoryIntelligent_Agent/architecture/architectureIssues/IssueFilters";
import IssueCard from "../../component/RepositoryIntelligent_Agent/architecture/architectureIssues/IssueCard";
import IssueDetails from "../../component/RepositoryIntelligent_Agent/architecture/architectureIssues/IssueDetails";

const ArchitectureIssues = () => {
  const [activeTab, setActiveTab] = useState("all");

  const [selectedIssue, setSelectedIssue] = useState(issues[0]);

  const [search, setSearch] = useState("");

  const [severity, setSeverity] = useState("All");

  const [type, setType] = useState("All");

  const [layer, setLayer] = useState("All");

  const [resolvedIds, setResolvedIds] = useState([]);

  const filteredIssues = useMemo(() => {
    return issues.filter((issue) => {
      if (
        activeTab !== "all" &&
        activeTab !== "Resolved" &&
        issue.severity !== activeTab
      ) {
        return false;
      }

      if (activeTab === "Resolved" && !resolvedIds.includes(issue.id)) {
        return false;
      }

      if (severity !== "All" && issue.severity !== severity) {
        return false;
      }

      if (type !== "All" && issue.type !== type) {
        return false;
      }

      if (layer !== "All" && issue.layer !== layer) {
        return false;
      }

      if (search.trim()) {
        const query = search.toLowerCase();

        const searchable = `
          ${issue.title}
          ${issue.subtitle}
          ${issue.description}
          ${issue.type}
          ${issue.layer}
        `.toLowerCase();

        if (!searchable.includes(query)) {
          return false;
        }
      }

      return true;
    });
  }, [activeTab, severity, type, layer, search, resolvedIds]);

  const handleResolve = (id) => {
    setResolvedIds((current) => [...current, id]);
  };

  return (
    <div className="w-full">
      <header className="mb-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-500">
              <AlertTriangle size={27} />
            </div>

            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                Architecture Issues
              </h1>

              <p className="mt-1 text-[10px] text-slate-500">
                Identify and resolve architectural violations and design
                problems
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <IssueSummaryCard
              type="total"
              title="Total Issues"
              value={issueSummary.total}
              subtitle="Architecture issues"
              change="↑ 2 since last scan"
            />

            <IssueSummaryCard
              type="high"
              title="High Severity"
              value={issueSummary.high}
              subtitle="33% of total"
            />

            <IssueSummaryCard
              type="health"
              title="Architecture Health"
              value={issueSummary.architectureHealth}
              subtitle="/ 100"
              change="+6 from last scan"
            />
          </div>
        </div>
      </header>

      <section className="border-b border-slate-200">
        <div className="flex flex-col gap-2 xl:flex-row xl:items-end xl:justify-between">
          <IssueTabs activeTab={activeTab} onChange={setActiveTab} />

          <IssueFilters
            search={search}
            setSearch={setSearch}
            severity={severity}
            setSeverity={setSeverity}
            type={type}
            setType={setType}
            layer={layer}
            setLayer={setLayer}
          />
        </div>
      </section>

      <main
        className="
          mt-3
          grid
          grid-cols-1
          gap-3
          xl:grid-cols-[0.95fr_1fr]
        "
      >
        {/* LEFT */}
        <section
          className="
            rounded-xl
            border border-slate-200
            bg-white
            p-3
            shadow-sm
          "
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">
              Architecture Issues
            </h2>

            <select
              className="
                rounded-md
                border border-slate-200
                bg-white
                px-2 py-1.5
                text-[8px]
                font-medium
                text-slate-600
                outline-none
              "
            >
              <option>Sort by: Severity</option>

              <option>Sort by: Confidence</option>

              <option>Sort by: Date</option>
            </select>
          </div>

          <div className="space-y-2">
            {filteredIssues.length > 0 ? (
              filteredIssues.map((issue) => (
                <IssueCard
                  key={issue.id}
                  issue={issue}
                  selected={selectedIssue?.id === issue.id}
                  onClick={setSelectedIssue}
                />
              ))
            ) : (
              <div className="flex h-40 items-center justify-center">
                <p className="text-xs text-slate-400">
                  No architecture issues found.
                </p>
              </div>
            )}
          </div>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-center gap-2">
            <button className="pagination-button">‹</button>

            <button className="pagination-button active">1</button>

            <button className="pagination-button">2</button>

            <button className="pagination-button">Next →</button>
          </div>
        </section>

        {/* RIGHT */}
        <IssueDetails issue={selectedIssue} onResolve={handleResolve} />
      </main>
    </div>
  );
};

export default ArchitectureIssues;
