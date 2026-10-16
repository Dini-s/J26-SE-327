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
import { repositoryStats } from "../../data/repositoryData";

const RepositoryAgentOverView = () => {
  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <RepositoryHeader />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {repositoryStats.map((stat) => (
          <RepositoryStatCard key={stat.title} {...stat} />
        ))}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[1.25fr_1fr_1fr]">
        <ArchitectureRiskTrend />

        <HighRiskModules />

        <AIInsightSummary />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[1.1fr_0.85fr_1.1fr]">
        <RepositoryEvolution />

        <ArchitectureIssues />

        <RecentCodeChanges />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[1fr_1.2fr]">
        <HRIMModelSummary />

        <DataSummary />
      </div>
    </div>
  );
};

export default RepositoryAgentOverView;
