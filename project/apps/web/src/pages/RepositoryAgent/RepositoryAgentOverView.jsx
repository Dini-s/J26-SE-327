import { useRepository } from "../../context/RepositoryContext";
import AIInsightSummary from "../../component/RepositoryIntelligent_Agent/agentOverview/AIInsightSummary";
import ArchitectureIssues from "../../component/RepositoryIntelligent_Agent/agentOverview/ArchitectureIssues";
import ArchitectureRiskTrend from "../../component/RepositoryIntelligent_Agent/agentOverview/ArchitectureRiskTrend";
import DataSummary from "../../component/RepositoryIntelligent_Agent/agentOverview/DataSummary";
import HighRiskModules from "../../component/RepositoryIntelligent_Agent/agentOverview/HighRiskModules";
import HRIMModelSummary from "../../component/RepositoryIntelligent_Agent/agentOverview/HRIMModelSummary";
import RecentCodeChanges from "../../component/RepositoryIntelligent_Agent/agentOverview/RecentCodeChanges";
import RepositoryEvolution from "../../component/RepositoryIntelligent_Agent/agentOverview/RepositoryEvolution";
import RepositoryHeader from "../../component/RepositoryIntelligent_Agent/agentOverview/RepositoryHeader";
import RepositoryStatCard from "../../component/RepositoryIntelligent_Agent/agentOverview/RepositoryStatCard";
import { getRepositoryDashboardData } from "../../data/repositoryDashboardData";

const RepositoryAgentOverView = () => {
  const { analysisResults, analyzing, selectedRepository } = useRepository();
  const data = getRepositoryDashboardData(analysisResults);
  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-3">
      <RepositoryHeader />
      {!analysisResults && !analyzing && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
          {selectedRepository
            ? `Selected: ${selectedRepository.name || selectedRepository.url || "Repository"}. Run Analyze Repository to load live dashboard metrics.`
            : "Choose a registered repository, then run an analysis to populate this dashboard."}
        </div>
      )}
      {analyzing && (
        <div
          role="status"
          className="rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-700"
        >
          Analyzing repository. Dashboard data will update when the backend
          returns its results.
        </div>
      )}
      {analysisResults && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {data.statCards.map((stat) => (
              <RepositoryStatCard key={stat.title} {...stat} />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.25fr_1fr_1fr]">
            <ArchitectureRiskTrend riskRows={data.riskRows} />
            <HighRiskModules riskRows={data.riskRows} />
            <AIInsightSummary
              findings={data.findings}
              riskRows={data.riskRows}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.1fr_0.85fr_1.1fr]">
            <RepositoryEvolution metrics={data.evolutionMetrics} />
            <ArchitectureIssues issues={data.issues} />
            <RecentCodeChanges changes={data.recentChanges} />
          </div>
          <div className="grid grid-cols-1 gap-3 ">
            <HRIMModelSummary />
            <DataSummary items={data.dataSummary} />
          </div>
        </>
      )}
    </div>
  );
};
export default RepositoryAgentOverView;
