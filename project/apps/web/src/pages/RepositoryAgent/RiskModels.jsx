import { useMemo, useState } from "react";
import { riskModules, riskStats } from "../../data/riskModules";
import ContentHeader from "../../component/common/ContentHeader";
import RiskStatCard from "../../component/RepositoryIntelligent_Agent/risk/RiskStatCard";
import RiskModuleFilters from "../../component/RepositoryIntelligent_Agent/risk/RiskModuleFilters";
import RiskModuleTable from "../../component/RepositoryIntelligent_Agent/risk/RiskModuleTable";
import RiskModuleDetail from "../../component/RepositoryIntelligent_Agent/risk/RiskModuleDetail";
import RiskDistribution from "../../component/RepositoryIntelligent_Agent/risk/RiskDistribution";
import DriftDistribution from "../../component/RepositoryIntelligent_Agent/risk/DriftDistribution";
import TopRiskPackages from "../../component/RepositoryIntelligent_Agent/risk/TopRiskPackages";
import RiskInsights from "../../component/RepositoryIntelligent_Agent/risk/RiskInsights";

const RiskModules = () => {
  const [search, setSearch] = useState("");

  const [selectedModule, setSelectedModule] = useState(riskModules[0]);

  const filteredModules = useMemo(() => {
    const query = search.toLowerCase().trim();

    if (!query) {
      return riskModules;
    }

    return riskModules.filter(
      (module) =>
        module.name.toLowerCase().includes(query) ||
        module.package.toLowerCase().includes(query) ||
        module.risk.toLowerCase().includes(query),
    );
  }, [search]);

  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <ContentHeader
        title={"Risk Modules"}
        subtitle={
          "Identify and Analyze high-risk modules based on architecture drift and software mertics"
        }
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {riskStats.map((stat) => (
          <RiskStatCard key={stat.title} {...stat} />
        ))}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,2.4fr)_minmax(350px,1fr)]">
        {/* Module List */}
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-4">
            <h2 className="text-sm font-semibold text-slate-900">
              High-Risk Module List
            </h2>
          </div>

          <RiskModuleFilters search={search} setSearch={setSearch} />

          <RiskModuleTable
            modules={filteredModules}
            selectedModule={selectedModule}
            onSelect={setSelectedModule}
          />

          {/* Pagination */}
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
            <p className="text-[9px] text-slate-500">
              Showing 1 to 8 of 38 modules
            </p>

            <div className="flex items-center gap-1">
              <button className="page-button">‹</button>

              <button className="page-button active">1</button>

              <button className="page-button">2</button>

              <button className="page-button">3</button>

              <button className="page-button">4</button>

              <button className="page-button">5</button>

              <button className="page-button">›</button>
            </div>
          </div>
        </section>

        {/* Module Detail */}
        <RiskModuleDetail module={selectedModule} />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-4">
        <RiskDistribution />

        <DriftDistribution />

        <TopRiskPackages />

        <RiskInsights />
      </div>
    </div>
  );
};

export default RiskModules;
