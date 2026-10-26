
import { useMemo, useState } from "react";
import ContentHeader from "../../component/common/ContentHeader";
import ArchitectureGraph from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureGraph";
import ArchitectureStatCard from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureStatCard";
import ArchitectureToolbar from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureToolbar";
import ArchitectureLegend from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureLegend";
import SelectedModulePanel from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/SelectedModulePanel";
import { useRepository } from "../../context/RepositoryContext";


const safeNumber = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
};

const normalizePath = (value) =>
  String(value ?? "").replaceAll("\\", "/").replace(/\/+$/, "");

const getPackageLayer = (packagePath) => {
  const path = normalizePath(packagePath).toLowerCase();

  if (/\.controller(?:\.|$)|\.web(?:\.|$)|\.ui(?:\.|$)/.test(path)) {
    return "Presentation";
  }

  if (/\.service(?:\.|$)|\.business(?:\.|$)/.test(path)) {
    return "Service";
  }

  if (/\.repository(?:\.|$)|\.dao(?:\.|$)/.test(path)) {
    return "Repository";
  }

  if (/\.config(?:uration)?(?:\.|$)|\.infra(?:structure)?(?:\.|$)/.test(path)) {
    return "Infrastructure";
  }

  return "Package";
};

const buildArchitectureView = (analysisResults) => {
  if (!analysisResults) {
    return { nodes: [], edges: [], modules: [] };
  }

  const architecture = Array.isArray(analysisResults.architecture)
    ? analysisResults.architecture
    : [];

  const structure = Array.isArray(analysisResults.structure)
    ? analysisResults.structure
    : [];

  const dependencies = Array.isArray(analysisResults.dependencies)
    ? analysisResults.dependencies
    : [];

  const predictions = Array.isArray(
    analysisResults.multimodal_proxy_predictions?.predictions
  )
    ? analysisResults.multimodal_proxy_predictions.predictions
    : [];

  const architectureByPath = new Map(
    architecture.map((item) => [normalizePath(item.package_path), item])
  );

  const structureByPath = new Map(
    structure.map((item) => [normalizePath(item.package_path), item])
  );

  const predictionByPath = new Map(
    predictions.map((item) => [normalizePath(item.package_path), item])
  );

  const packagePaths = [
    ...new Set([
      ...architecture.map((item) => normalizePath(item.package_path)),
      ...structure.map((item) => normalizePath(item.package_path)),
      ...dependencies.flatMap((item) => [
        normalizePath(item.source_package),
        normalizePath(item.target_package),
      ]),
    ]),
  ].filter(Boolean);

  const modules = packagePaths.map((packagePath, index) => {
    const metric = architectureByPath.get(packagePath) || {};
    const structureMetric = structureByPath.get(packagePath) || {};
    const prediction = predictionByPath.get(packagePath);

    const name = packagePath.split("/").filter(Boolean).at(-1) || packagePath;

    return {
      id: `package-${index}`,
      name,
      package: packagePath,
      layer: getPackageLayer(packagePath),
      javaFiles: safeNumber(metric.java_files ?? structureMetric.java_files),
      linesOfCode: safeNumber(
        metric.lines_of_code ?? structureMetric.lines_of_code
      ),
      fanIn: safeNumber(metric.fan_in),
      fanOut: safeNumber(metric.fan_out),
      totalCoupling: safeNumber(metric.total_coupling),
      instability:
        metric.instability === null || metric.instability === undefined
          ? null
          : safeNumber(metric.instability),
      proxyProbability:
        prediction?.proxy_probability === null ||
        prediction?.proxy_probability === undefined
          ? null
          : safeNumber(prediction.proxy_probability),
      predictedProxyLabel: prediction?.predicted_proxy_label,
      interpretation: prediction?.interpretation,
      position: {
        x: (index % 3) * 240,
        y: Math.floor(index / 3) * 150,
      },
    };
  });

  const idByPath = new Map(
    modules.map((module) => [module.package, module.id])
  );

  const nodes = modules.map((module) => ({
    id: module.id,
    type: "architecture",
    position: module.position,
    data: module,
  }));

  const edgeKeys = new Set();

  const edges = dependencies.flatMap((dependency, index) => {
    const sourcePath = normalizePath(dependency.source_package);
    const targetPath = normalizePath(dependency.target_package);
    const source = idByPath.get(sourcePath);
    const target = idByPath.get(targetPath);

    if (!source || !target || source === target) return [];

    const key = `${source}->${target}`;
    if (edgeKeys.has(key)) return [];
    edgeKeys.add(key);

    return [{
      id: `dependency-${index}-${source}-${target}`,
      source,
      target,
      violation: false,
    }];
  });

  return { nodes, edges, modules };
};

const ArchitectureVisualization = () => {
  const { analysisResults, selectedRepository } = useRepository();

  const { nodes, edges, modules } = useMemo(
    () => buildArchitectureView(analysisResults),
    [analysisResults]
  );

  const [selectedModuleId, setSelectedModuleId] = useState(null);

  const selectedModule =
    modules.find((module) => module.id === selectedModuleId) ??
    modules[0] ??
    null;

  const stats = [
    {
      title: "Packages Analyzed",
      value: modules.length,
      status: "Packages returned by analysis",
      type: "blue",
      icon: "structure",
    },
    {
      title: "Dependency Edges",
      value: edges.length,
      status: "Unique package relationships",
      type: "purple",
      icon: "dependency",
    },
    {
      title: "Files With Evolution",
      value: analysisResults?.file_evolution_count ?? "—",
      status: "Files reported by the API",
      type: "green",
      icon: "files",
    },
    {
      title: "Proxy Predictions",
      value: modules.filter(
        (module) => module.proxyProbability !== null
      ).length,
      status: "Exploratory HRIM outputs",
      type: "orange",
      icon: "warning",
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <header className="mb-4">
        <ContentHeader
          title="Architecture Visualization"
          subtitle="Explore package structure, dependencies, architecture metrics, and exploratory HRIM predictions"
        />
      </header>

      {!analysisResults ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-800">
            No analysis results available
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            {selectedRepository
              ? "Run the repository analysis to display its architecture."
              : "Select a repository and run its analysis to display the architecture."}
          </p>
        </div>
      ) : (
        <>
          <section className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((stat) => (
              <ArchitectureStatCard key={stat.title} {...stat} />
            ))}
          </section>

          <section className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.9fr)_minmax(330px,0.8fr)]">
            <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <ArchitectureToolbar />
              <ArchitectureLegend />
              <ArchitectureGraph
                nodes={nodes}
                edges={edges}
                onSelectModule={(module) => setSelectedModuleId(module.id)}
              />
            </div>

            <SelectedModulePanel module={selectedModule} edges={edges} />
          </section>

          <p className="mt-3 text-xs leading-5 text-slate-500">
            Proxy scores are exploratory model outputs, not confirmed
            architecture violations. Historical trends and validated
            architecture-health scores are not available from this API response.
          </p>
        </>
      )}
    </div>
  );
};

export default ArchitectureVisualization;
