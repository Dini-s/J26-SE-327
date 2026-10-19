import ContentHeader from "../../component/common/ContentHeader";
import AnalysisHistory from "../../component/RepositoryIntelligent_Agent/Evalution/AnalysisHistory";
import ArchitectureIssuesImpact from "../../component/RepositoryIntelligent_Agent/Evalution/ArchitectureIssuesImpact";
import CodeChurnChart from "../../component/RepositoryIntelligent_Agent/Evalution/CodeChurnChart";
import DependencyOverview from "../../component/RepositoryIntelligent_Agent/Evalution/DependencyOverview";
import EvolutionStatCard from "../../component/RepositoryIntelligent_Agent/Evalution/EvolutionStatCard";
import EvolutionTrend from "../../component/RepositoryIntelligent_Agent/Evalution/EvolutionTrend";
import HighRiskModules from "../../component/RepositoryIntelligent_Agent/Evalution/HighRiskModules";
import SoftwareMetricsSummary from "../../component/RepositoryIntelligent_Agent/Evalution/SoftwareMetricsSummary";
import TopMetricsByModule from "../../component/RepositoryIntelligent_Agent/Evalution/TopMetricsByModule";
import { evolutionStats } from "../../data/evolutionData";

const EvolutionOverview = () => {
  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <header className="mb-1">
        <ContentHeader
          title={"Evolution & Metrics"}
          subtitle={"All the metrics and evalution analyze"}
        />
      </header>

      <section className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {evolutionStats.map((stat) => (
          <EvolutionStatCard key={stat.title} {...stat} />
        ))}
      </section>

      <section className="mt-2 grid grid-cols-1 gap-2 xl:grid-cols-[1fr_1.2fr]">
        <EvolutionTrend />

        <SoftwareMetricsSummary />
      </section>

      <section className="mt-2 grid grid-cols-1 gap-2 xl:grid-cols-[1.15fr_0.72fr_1.0fr]">
        <HighRiskModules />

        <CodeChurnChart />

        <TopMetricsByModule />
      </section>

      <section className="mt-2 grid grid-cols-1 gap-2 lg:grid-cols-2 xl:grid-cols-[0.9fr_0.9fr_2.3fr]">
        <ArchitectureIssuesImpact />

        <DependencyOverview />

        <AnalysisHistory />
      </section>
    </div>
  );
};

export default EvolutionOverview;
