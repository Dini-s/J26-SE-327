
import { useEffect, useMemo, useState } from "react";
import { AlertCircle } from "lucide-react";

import ContentHeader from "../../component/common/ContentHeader";
import RiskStatCard from "../../component/RepositoryIntelligent_Agent/risk/RiskStatCard";
import RiskModuleFilters from "../../component/RepositoryIntelligent_Agent/risk/RiskModuleFilters";
import RiskModuleTable from "../../component/RepositoryIntelligent_Agent/risk/RiskModuleTable";
import RiskModuleDetail from "../../component/RepositoryIntelligent_Agent/risk/RiskModuleDetail";
import RiskDistribution from "../../component/RepositoryIntelligent_Agent/risk/RiskDistribution";
import DriftDistribution from "../../component/RepositoryIntelligent_Agent/risk/DriftDistribution";
import TopRiskPackages from "../../component/RepositoryIntelligent_Agent/risk/TopRiskPackages";
import RiskInsights from "../../component/RepositoryIntelligent_Agent/risk/RiskInsights";
import { useRepository } from "../../context/RepositoryContext";

const getRiskLevel = (probability) => {
  if (probability >= 0.6) return "HIGH";
  if (probability >= 0.4) return "MEDIUM";
  return "LOW";
};

const RiskModules = () => {
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [sortOrder, setSortOrder] = useState("DEFAULT");
  const [selectedModuleId, setSelectedModuleId] = useState(null);

  const {
    selectedRepository,
    analysisResults,
    analyzing,
    analysisError,
  } = useRepository();

  // Transform the actual API response into the package table format.
  const modules = useMemo(() => {
    const architecture = analysisResults?.architecture ?? [];
    const predictions =
      analysisResults?.multimodal_proxy_predictions?.predictions ?? [];

    if (!Array.isArray(architecture) || !Array.isArray(predictions)) {
      return [];
    }

    const predictionByPackage = new Map(
      predictions.map((item) => [item.package_path, item])
    );

    return architecture.map((item, index) => {
      const prediction = predictionByPackage.get(item.package_path);

      const probability =
        typeof prediction?.proxy_probability === "number" &&
        Number.isFinite(prediction.proxy_probability)
          ? prediction.proxy_probability
          : null;

      const coupling = Number(item.total_coupling ?? 0);
      const churn = Number(
        analysisResults?.evolution?.[0]?.total_churn ?? 0
      );

      return {
        id: item.package_path || index,
        name: item.package_path?.split(".").pop() || "Unknown package",
        package: item.package_path || "Unknown package",
        risk: probability === null ? "—" : getRiskLevel(probability),
        proxyProbability: probability,
        drift:
          probability === null
            ? null
            : Number((probability * 100).toFixed(2)),
        complexity: "—",
        coupling:
          coupling >= 3 ? "High" : coupling >= 1 ? "Medium" : "Low",
        churn: churn > 0 ? "Available" : "Unavailable",
        javaFiles: Number(item.java_files ?? 0),
        linesOfCode: Number(item.lines_of_code ?? 0),
        fanIn: Number(item.fan_in ?? 0),
        fanOut: Number(item.fan_out ?? 0),
        instability: Number(item.instability ?? 0),
        trend: [],
        predictionLabel: prediction?.predicted_proxy_label ?? null,
      };
    });
  }, [analysisResults]);

  // Reset search and filters when the selected repository changes.
  useEffect(() => {
    setSearch("");
    setRiskFilter("ALL");
    setSortOrder("DEFAULT");
  }, [selectedRepository?.id]);

  // Filter and sort packages.
  const filteredModules = useMemo(() => {
    const query = search.toLowerCase().trim();

    let result = modules.filter((module) => {
      const matchesSearch = [
        module.name,
        module.package,
        module.risk,
      ].some((value) =>
        String(value ?? "").toLowerCase().includes(query)
      );

      const matchesRisk =
        riskFilter === "ALL" ||
        (riskFilter === "UNSCORED" &&
          module.proxyProbability === null) ||
        (riskFilter !== "UNSCORED" &&
          riskFilter !== "ALL" &&
          module.risk === riskFilter);

      return matchesSearch && matchesRisk;
    });

    if (sortOrder === "DESC") {
      result = [...result].sort((a, b) => {
        if (a.proxyProbability === null) return 1;
        if (b.proxyProbability === null) return -1;
        return b.proxyProbability - a.proxyProbability;
      });
    } else if (sortOrder === "ASC") {
      result = [...result].sort((a, b) => {
        if (a.proxyProbability === null) return 1;
        if (b.proxyProbability === null) return -1;
        return a.proxyProbability - b.proxyProbability;
      });
    }

    return result;
  }, [modules, search, riskFilter, sortOrder]);

  // Preserve the selected package while it still exists.
  useEffect(() => {
    setSelectedModuleId((currentId) => {
      const stillExists = modules.some(
        (module) => module.id === currentId
      );

      return stillExists ? currentId : modules[0]?.id ?? null;
    });
  }, [modules]);

  const selectedModule =
    filteredModules.find((module) => module.id === selectedModuleId) ??
    filteredModules[0] ??
    null;

  // Only scored packages contribute to proxy-score statistics.
  const predictions = modules.filter(
    (module) => module.proxyProbability !== null
  );

  const highRisk = predictions.filter(
    (module) => module.risk === "HIGH"
  );

  const mediumRisk = predictions.filter(
    (module) => module.risk === "MEDIUM"
  );

  const lowRisk = predictions.filter(
    (module) => module.risk === "LOW"
  );

  const averageProbability = predictions.length
    ? predictions.reduce(
        (sum, module) => sum + module.proxyProbability,
        0
      ) / predictions.length
    : null;

  const criticalModule = predictions.reduce(
    (highest, module) =>
      !highest || module.proxyProbability > highest.proxyProbability
        ? module
        : highest,
    null
  );

  const riskStats = [
    {
      title: "High-Risk Proxy Scores",
      value: String(highRisk.length),
      description: "Score ≥ 60%",
      type: "red",
      icon: "warning",
    },
    {
      title: "Medium-Risk Proxy Scores",
      value: String(mediumRisk.length),
      description: "Score 40–59.99%",
      type: "orange",
      icon: "shield",
    },
    {
      title: "Low-Risk Proxy Scores",
      value: String(lowRisk.length),
      description: "Score < 40%",
      type: "green",
      icon: "shield",
    },
    {
      title: "Average Proxy Score",
      value:
        averageProbability === null
          ? "—"
          : `${(averageProbability * 100).toFixed(1)}%`,
      description: "Across scored packages",
      type: "purple",
      icon: "drift",
    },
    {
      title: "Highest Proxy Score",
      value: criticalModule?.name ?? "—",
      description: criticalModule
        ? `${(criticalModule.proxyProbability * 100).toFixed(2)}%`
        : "No predictions available",
      type: "red",
      icon: "critical",
    },
    {
      title: "Packages Analyzed",
      value: String(modules.length),
      description: "From current API response",
      type: "blue",
      icon: "cube",
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <ContentHeader
        title="Risk Modules"
        subtitle="Explore package structure, coupling, and model proxy scores for the selected repository."
      />

      {/* Analysis status and error messages */}
      {analysisError && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle size={17} className="mt-0.5 shrink-0" />
          <span>{analysisError}</span>
        </div>
      )}

      {analyzing && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-700">
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
          Repository analysis is running.
        </div>
      )}

      {analysisResults && modules.length === 0 && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          No package architecture results were found in this analysis response.
        </div>
      )}

      {!analysisResults && !analyzing && !analysisError && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
          <AlertCircle size={17} className="mt-0.5 shrink-0" />
          Select a repository and run analysis to display its results.
        </div>
      )}

      {/* Summary statistics */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {riskStats.map((stat) => (
          <RiskStatCard key={stat.title} {...stat} />
        ))}
      </div>

      {/* Package table and selected package details */}
      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,2.4fr)_minmax(350px,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-4">
            <h2 className="text-sm font-semibold text-slate-900">
              Package Analysis
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              {selectedRepository?.name || "Selected repository"}
            </p>
          </div>

          <RiskModuleFilters
            search={search}
            setSearch={setSearch}
            riskFilter={riskFilter}
            setRiskFilter={setRiskFilter}
            sortOrder={sortOrder}
            setSortOrder={setSortOrder}
          />

          <RiskModuleTable
            modules={filteredModules}
            selectedModule={selectedModule}
            onSelect={(module) => setSelectedModuleId(module.id)}
          />

          <div className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
            Showing {filteredModules.length} of {modules.length} packages
          </div>
        </section>

        <RiskModuleDetail module={selectedModule} />
      </div>

      {/* Consistent light-theme chart grid */}
      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <RiskDistribution modules={modules} />
        <DriftDistribution modules={modules} />
        <TopRiskPackages modules={modules} />
        <RiskInsights modules={modules} />
      </div>
    </div>
  );
};

export default RiskModules;
