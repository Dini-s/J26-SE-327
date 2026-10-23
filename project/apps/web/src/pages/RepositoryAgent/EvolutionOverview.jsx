import { useMemo } from "react";
import {
  Activity,
  Boxes,
  GitBranch,
  GitCommit,
  Info,
  Package,
  RefreshCw,
  Users,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import ContentHeader from "../../component/common/ContentHeader";
import { useRepository } from "../../context/RepositoryContext";

const formatNumber = (value) => {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const number = Number(value);

  return Number.isFinite(number) ? number.toLocaleString() : String(value);
};

const getNumber = (value) => {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const number = Number(value);

  return Number.isFinite(number) ? number : null;
};

const getField = (item, ...keys) => {
  if (!item || typeof item !== "object") return undefined;

  for (const key of keys) {
    if (item[key] !== undefined && item[key] !== null) {
      return item[key];
    }
  }

  return undefined;
};

const MetricCard = ({ title, value, subtitle, icon: Icon, color }) => (
  <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <p className="mt-2 break-words text-2xl font-bold text-slate-900">
          {value}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">
          {subtitle}
        </p>
      </div>

      <div className={`rounded-lg p-2 ${color}`}>
        <Icon size={20} />
      </div>
    </div>
  </section>
);

const Section = ({ title, description, children, action }) => (
  <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
      <div>
        <h2 className="text-sm font-bold text-slate-900">{title}</h2>
        {description && (
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>

    {children}
  </section>
);

const EmptyMessage = ({ children }) => (
  <div className="rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500">
    {children}
  </div>
);

const EvolutionOverview = () => {
  const navigate = useNavigate();

  const { selectedRepository, analysisResults } = useRepository();

  const hasAnalysis = Boolean(analysisResults);

  const structure = Array.isArray(analysisResults?.structure)
    ? analysisResults.structure
    : [];

  const dependencies = Array.isArray(analysisResults?.dependencies)
    ? analysisResults.dependencies
    : [];

  const architecture = Array.isArray(analysisResults?.architecture)
    ? analysisResults.architecture
    : [];

  // Repository-wide Git history metrics are separate from per-file metrics.
  const evolutionSummary = analysisResults?.evolution_summary || {};

  const fileEvolution = Array.isArray(analysisResults?.file_evolution)
    ? analysisResults.file_evolution
    : [];

  // Keep the legacy field as a fallback for older cached analysis responses.
  const legacyEvolution = Array.isArray(analysisResults?.evolution)
    ? analysisResults.evolution
    : [];

  const findings = Array.isArray(analysisResults?.architecture_findings)
    ? analysisResults.architecture_findings
    : [];

  const predictions = Array.isArray(
    analysisResults?.multimodal_proxy_predictions?.predictions,
  )
    ? analysisResults.multimodal_proxy_predictions.predictions
    : [];

  const summary = analysisResults?.summary || {};

  const metrics = useMemo(() => {
    const scoredPredictions = predictions.filter((item) => {
      const probability = getField(
        item,
        "proxy_probability",
        "proxyProbability",
      );

      return typeof probability === "number" && Number.isFinite(probability);
    });

    const highProxyScores = scoredPredictions.filter((item) => {
      const score = getField(item, "proxy_probability", "proxyProbability");
      return score >= 0.6;
    }).length;

    const mediumProxyScores = scoredPredictions.filter((item) => {
      const score = getField(item, "proxy_probability", "proxyProbability");
      return score >= 0.4 && score < 0.6;
    }).length;

    const lowProxyScores = scoredPredictions.filter((item) => {
      const score = getField(item, "proxy_probability", "proxyProbability");
      return score < 0.4;
    }).length;

    const totalCouplingValues = architecture
      .map((item) => getNumber(item.total_coupling))
      .filter((value) => value !== null);

    const averageCoupling = totalCouplingValues.length
      ? totalCouplingValues.reduce((sum, value) => sum + value, 0) /
        totalCouplingValues.length
      : null;

    const totalEdges = dependencies.length;

    const candidateFindings = findings.filter(
      (item) =>
        String(item.status || "Candidate").toLowerCase() === "candidate",
    ).length;

    const confirmedFindings = findings.filter(
      (item) => String(item.status || "").toLowerCase() === "confirmed",
    ).length;

    return {
      packageCount: getNumber(summary.packages) ?? structure.length,

      architecturePackageCount:
        getNumber(summary.architecture_packages) ?? architecture.length,

      dependencyCount: getNumber(summary.dependency_edges) ?? totalEdges,

      filesWithEvolution:
        getNumber(summary.files_with_evolution) ??
        getNumber(analysisResults?.file_evolution_count),

      evolutionRecords: fileEvolution.length || legacyEvolution.length,

      averageCoupling,

      scoredPackages: scoredPredictions.length,
      highProxyScores,
      mediumProxyScores,
      lowProxyScores,

      candidateFindings,
      confirmedFindings,
      totalFindings: findings.length,
    };
  }, [
    analysisResults,
    summary,
    structure,
    dependencies,
    architecture,
    fileEvolution,
    legacyEvolution,
    findings,
    predictions,
  ]);

  const packageRows = useMemo(() => {
    return architecture.map((item) => {
      const packageName = getField(
        item,
        "package",
        "package_name",
        "packageName",
        "module",
        "name",
      );

      const prediction = predictions.find((candidate) => {
        const predictedPackage = getField(
          candidate,
          "package",
          "package_name",
          "packageName",
          "module",
          "name",
        );

        return (
          predictedPackage !== undefined &&
          packageName !== undefined &&
          predictedPackage === packageName
        );
      });

      const proxyProbability = getNumber(
        getField(prediction, "proxy_probability", "proxyProbability"),
      );

      return {
        name: packageName || "Unnamed package",
        fanIn: getField(item, "fan_in", "fanIn"),
        fanOut: getField(item, "fan_out", "fanOut"),
        coupling: getField(item, "total_coupling", "totalCoupling"),
        instability: getField(item, "instability"),
        proxyProbability,
      };
    });
  }, [architecture, predictions]);

  const proxyBands = [
    {
      label: "High",
      count: metrics.highProxyScores,
      color: "bg-rose-500",
      dot: "bg-rose-500",
    },
    {
      label: "Medium",
      count: metrics.mediumProxyScores,
      color: "bg-amber-500",
      dot: "bg-amber-500",
    },
    {
      label: "Low",
      count: metrics.lowProxyScores,
      color: "bg-emerald-500",
      dot: "bg-emerald-500",
    },
  ];

  const maximumProxyCount = Math.max(
    metrics.highProxyScores,
    metrics.mediumProxyScores,
    metrics.lowProxyScores,
    1,
  );

  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-4">
      <header>
        <ContentHeader
          title="Evolution & Metrics"
          subtitle="Repository structure, dependency relationships, evolution data, and exploratory HRIM results"
        />

        {selectedRepository && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Package size={14} />
            <span>Repository:</span>
            <span className="font-semibold text-slate-700">
              {selectedRepository.name || selectedRepository.id}
            </span>

            {analysisResults?.status && (
              <span className="rounded-full bg-emerald-50 px-2 py-1 font-medium text-emerald-700">
                {analysisResults.status}
              </span>
            )}
          </div>
        )}
      </header>

      {!hasAnalysis ? (
        <section className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
            <Activity size={24} />
          </div>

          <h2 className="mt-4 text-base font-semibold text-slate-900">
            No repository analysis available
          </h2>

          <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-slate-500">
            Select a repository and run its analysis from the Repositories page.
            The available metrics will appear here when the analysis results are
            loaded into RepositoryContext.
          </p>

          <button
            type="button"
            onClick={() => navigate("/repository")}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            <RefreshCw size={15} />
            Go to Repositories
          </button>
        </section>
      ) : (
        <>
          {/* Summary cards */}
          <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              title="Structural Packages"
              value={formatNumber(metrics.packageCount)}
              subtitle="Packages found by structural analysis"
              icon={Boxes}
              color="bg-blue-50 text-blue-600"
            />

            <MetricCard
              title="Dependency Edges"
              value={formatNumber(metrics.dependencyCount)}
              subtitle="Relationships returned by the dependency analyzer"
              icon={GitBranch}
              color="bg-purple-50 text-purple-600"
            />

            <MetricCard
              title="Architecture Records"
              value={formatNumber(metrics.architecturePackageCount)}
              subtitle="Package-level architecture metric records"
              icon={Activity}
              color="bg-emerald-50 text-emerald-600"
            />

            <MetricCard
              title="Files With Evolution"
              value={formatNumber(metrics.filesWithEvolution)}
              subtitle="Files represented in the evolution analysis"
              icon={GitCommit}
              color="bg-amber-50 text-amber-600"
            />
          </section>

          {/* Repository-wide Git evolution metrics */}
          <Section
            title="Repository Evolution Metrics"
            description="Repository-wide metrics calculated from the available Git history. Change records are not the same as unique files."
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <MetricCard
                title="Total Commits"
                value={formatNumber(evolutionSummary.commit_count)}
                subtitle="Commits in the available Git history"
                icon={GitCommit}
                color="bg-blue-50 text-blue-600"
              />
              <MetricCard
                title="Contributors"
                value={formatNumber(evolutionSummary.contributor_count)}
                subtitle="Contributors found in Git history"
                icon={Users}
                color="bg-purple-50 text-purple-600"
              />
              <MetricCard
                title="Change Records"
                value={formatNumber(evolutionSummary.files_changed)}
                subtitle="File-change records across history; not unique files"
                icon={GitBranch}
                color="bg-amber-50 text-amber-600"
              />
              <MetricCard
                title="Total Insertions"
                value={formatNumber(evolutionSummary.total_insertions)}
                subtitle="Lines added across recorded changes"
                icon={Activity}
                color="bg-emerald-50 text-emerald-600"
              />
              <MetricCard
                title="Total Deletions"
                value={formatNumber(evolutionSummary.total_deletions)}
                subtitle="Lines deleted across recorded changes"
                icon={Activity}
                color="bg-rose-50 text-rose-600"
              />
              <MetricCard
                title="Total Churn"
                value={formatNumber(evolutionSummary.total_churn)}
                subtitle="Insertions plus deletions"
                icon={GitCommit}
                color="bg-indigo-50 text-indigo-600"
              />
            </div>
            {!Object.keys(evolutionSummary).length && (
              <p className="mt-3 text-xs text-amber-700">
                Repository-wide evolution summary is not present in this
                analysis response. Run repository analysis again to load the
                latest results.
              </p>
            )}
          </Section>

          {/* Data coverage */}
          <Section
            title="Analysis Coverage"
            description="Coverage of the analysis outputs available for the selected repository."
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Structural records</p>
                <p className="mt-1 text-xl font-bold text-slate-900">
                  {formatNumber(structure.length)}
                </p>
              </div>

              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Evolution records</p>
                <p className="mt-1 text-xl font-bold text-slate-900">
                  {formatNumber(metrics.evolutionRecords)}
                </p>
              </div>

              <div className="rounded-lg bg-slate-50 p-3">
                <p className="text-xs text-slate-500">Average total coupling</p>
                <p className="mt-1 text-xl font-bold text-slate-900">
                  {metrics.averageCoupling === null
                    ? "—"
                    : metrics.averageCoupling.toFixed(2)}
                </p>
              </div>
            </div>
          </Section>

          {/* HRIM proxy score distribution */}
          <Section
            title="Package Proxy Score Bands"
            description="Exploratory HRIM proxy score distribution. These bands are not validated architecture-risk classifications."
            action={
              <button
                type="button"
                onClick={() => navigate("/repository/risk-models")}
                className="text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                View risk models →
              </button>
            }
          >
            {metrics.scoredPackages === 0 ? (
              <EmptyMessage>
                No numeric HRIM proxy predictions are available for this
                analysis.
              </EmptyMessage>
            ) : (
              <div className="grid grid-cols-1 gap-5 md:grid-cols-[180px_1fr] md:items-center">
                <div className="flex justify-center">
                  <div className="flex h-36 w-36 flex-col items-center justify-center rounded-full border-[10px] border-slate-100">
                    <span className="text-3xl font-bold text-slate-900">
                      {metrics.scoredPackages}
                    </span>
                    <span className="mt-1 text-center text-xs text-slate-500">
                      Scored packages
                    </span>
                  </div>
                </div>

                <div className="space-y-4">
                  {proxyBands.map((band) => {
                    const percentage =
                      (band.count / metrics.scoredPackages) * 100;

                    return (
                      <div key={band.label}>
                        <div className="mb-1.5 flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <span
                              className={`h-2.5 w-2.5 rounded-full ${band.dot}`}
                            />
                            <span className="text-slate-600">{band.label}</span>
                          </div>

                          <span className="font-medium text-slate-900">
                            {band.count} ({percentage.toFixed(0)}%)
                          </span>
                        </div>

                        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full transition-all ${band.color}`}
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Section>

          {/* Architecture findings */}
          <Section
            title="Architecture Findings"
            description="Only finding records returned by the backend are shown. Candidates are not treated as confirmed violations."
            action={
              <button
                type="button"
                onClick={() => navigate("/repository/issues")}
                className="text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                View issues →
              </button>
            }
          >
            {findings.length === 0 ? (
              <EmptyMessage>
                No architecture finding records were returned. This does not
                establish that the repository has no architectural issues.
              </EmptyMessage>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">Total findings</p>
                  <p className="mt-1 text-2xl font-bold text-slate-900">
                    {metrics.totalFindings}
                  </p>
                </div>

                <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                  <p className="text-xs text-amber-700">Candidates</p>
                  <p className="mt-1 text-2xl font-bold text-amber-800">
                    {metrics.candidateFindings}
                  </p>
                </div>

                <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3">
                  <p className="text-xs text-emerald-700">Confirmed</p>
                  <p className="mt-1 text-2xl font-bold text-emerald-800">
                    {metrics.confirmedFindings}
                  </p>
                </div>
              </div>
            )}
          </Section>

          {/* Package architecture metrics */}
          <Section
            title="Package Architecture Metrics"
            description="Package-level values returned by the architecture analyzer."
          >
            {packageRows.length === 0 ? (
              <EmptyMessage>
                No package architecture metrics are available.
              </EmptyMessage>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs text-slate-500">
                      <th className="px-3 py-3 font-medium">Package</th>
                      <th className="px-3 py-3 font-medium">Fan-in</th>
                      <th className="px-3 py-3 font-medium">Fan-out</th>
                      <th className="px-3 py-3 font-medium">Coupling</th>
                      <th className="px-3 py-3 font-medium">Instability</th>
                      <th className="px-3 py-3 font-medium">Proxy score</th>
                    </tr>
                  </thead>

                  <tbody>
                    {packageRows.map((item, index) => (
                      <tr
                        key={`${item.name}-${index}`}
                        className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                      >
                        <td className="max-w-[300px] break-all px-3 py-3 font-medium text-slate-800">
                          {item.name}
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {formatNumber(item.fanIn)}
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {formatNumber(item.fanOut)}
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {formatNumber(item.coupling)}
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {formatNumber(item.instability)}
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {item.proxyProbability === null
                            ? "—"
                            : item.proxyProbability.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {/* Dependency relationships */}
          <Section
            title="Dependency Overview"
            description="A summary of the dependency edges returned by the analyzer."
            action={
              <button
                type="button"
                onClick={() => navigate("/repository/dependencies")}
                className="text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                View dependency analysis →
              </button>
            }
          >
            {dependencies.length === 0 ? (
              <EmptyMessage>
                No dependency edges were returned by the analysis.
              </EmptyMessage>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-slate-500">Dependency edges</p>
                    <p className="mt-1 text-xl font-bold text-slate-900">
                      {dependencies.length}
                    </p>
                  </div>

                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-slate-500">
                      Distinct source packages
                    </p>
                    <p className="mt-1 text-xl font-bold text-slate-900">
                      {
                        new Set(
                          dependencies
                            .map((item) =>
                              getField(
                                item,
                                "source_package",
                                "sourcePackage",
                                "source",
                              ),
                            )
                            .filter(Boolean),
                        ).size
                      }
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-xs text-slate-500">
                        <th className="px-3 py-2 font-medium">
                          Source package
                        </th>
                        <th className="px-3 py-2 font-medium">
                          Target package
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {dependencies.slice(0, 10).map((edge, index) => (
                        <tr
                          key={`${index}-${JSON.stringify(edge)}`}
                          className="border-b border-slate-100 last:border-0"
                        >
                          <td className="break-all px-3 py-3 text-slate-700">
                            {getField(
                              edge,
                              "source_package",
                              "sourcePackage",
                              "source",
                            ) || "—"}
                          </td>
                          <td className="break-all px-3 py-3 text-slate-700">
                            {getField(
                              edge,
                              "target_package",
                              "targetPackage",
                              "target",
                            ) || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {dependencies.length > 10 && (
                    <p className="mt-2 text-xs text-slate-500">
                      Showing 10 of {dependencies.length} dependency edges.
                    </p>
                  )}
                </div>
              </div>
            )}
          </Section>

          {/* File-level evolution data */}
          <Section
            title="File-Level Evolution"
            description="Historical change metrics for individual files. These rows are separate from the repository-wide summary above."
          >
            {fileEvolution.length === 0 && legacyEvolution.length === 0 ? (
              <EmptyMessage>
                No file-level evolution records are available in this analysis
                response. Run repository analysis again to refresh the data.
              </EmptyMessage>
            ) : (
              <div className="overflow-x-auto">
                {(() => {
                  const records = fileEvolution.length
                    ? fileEvolution
                    : legacyEvolution;
                  const preferredKeys = [
                    "file_path",
                    "change_records",
                    "commit_count",
                    "total_insertions",
                    "total_deletions",
                    "total_churn",
                  ];
                  const keys = preferredKeys.filter((key) =>
                    Object.prototype.hasOwnProperty.call(records[0] || {}, key),
                  );
                  const columns = keys.length
                    ? keys
                    : Object.keys(records[0] || {}).slice(0, 6);

                  return (
                    <>
                      <table className="w-full min-w-[760px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 text-xs text-slate-500">
                            {columns.map((key) => (
                              <th key={key} className="px-3 py-3 font-medium">
                                {key.replaceAll("_", " ")}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {records.slice(0, 20).map((record, index) => (
                            <tr
                              key={`${record.file_path || record.repository || "evolution"}-${index}`}
                              className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                            >
                              {columns.map((key) => (
                                <td
                                  key={key}
                                  className="max-w-[320px] break-all px-3 py-3 text-slate-700"
                                >
                                  {key === "file_path"
                                    ? record[key] || "—"
                                    : formatNumber(record[key])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {records.length > 20 && (
                        <p className="mt-2 text-xs text-slate-500">
                          Showing 20 of {formatNumber(records.length)} file
                          evolution records.
                        </p>
                      )}
                    </>
                  );
                })()}
              </div>
            )}
          </Section>

          {/* Data limitations */}
          <div className="flex items-start gap-3 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
            <Info className="mt-0.5 shrink-0 text-blue-600" size={18} />

            <div>
              <h3 className="text-sm font-semibold text-blue-900">
                Interpretation and data availability
              </h3>

              <p className="mt-1 text-xs leading-relaxed text-blue-800">
                Architecture metrics and dependency relationships describe the
                current analysis output. HRIM proxy scores are exploratory. This
                dashboard does not calculate a validated architecture health
                score, invent historical trends, or treat candidate findings as
                confirmed defects.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default EvolutionOverview;
