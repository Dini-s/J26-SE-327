import { useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Boxes,
  Database,
  GitBranch,
  Link2,
  Search,
  ShieldAlert,
  Unplug,
  Workflow,
  X,
} from "lucide-react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useRepository } from "../../context/RepositoryContext";
import CircularDependencyCard from "../../component/RepositoryIntelligent_Agent/Dependencies/CircularDependencyCard";

const Stat = ({ icon: Icon, label, value, note, tone = "blue" }) => {
  const tones = {
    blue: "bg-blue-50 text-blue-700 ring-blue-100",
    violet: "bg-violet-50 text-violet-700 ring-violet-100",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
    rose: "bg-rose-50 text-rose-700 ring-rose-100",
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-slate-950">
            {value}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-400">{note}</p>
        </div>
        <div className={`rounded-xl p-2.5 ring-1 ${tones[tone]}`}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
};

function PackageNode({ data }) {
  const { label, incoming, outgoing, selected, coupling } = data;
  return (
    <div
      className={`min-w-[190px] rounded-2xl border bg-white shadow-lg transition ${selected ? "border-blue-500 ring-4 ring-blue-100" : "border-slate-200 hover:border-blue-300"}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2.5 !w-2.5 !border-2 !border-white !bg-blue-500"
      />
      <div
        className={`rounded-t-2xl px-3.5 py-3 ${selected ? "bg-blue-600 text-white" : "bg-slate-50 text-slate-800"}`}
      >
        <div className="flex items-center gap-2">
          <div
            className={`rounded-lg p-1.5 ${selected ? "bg-white/15" : "bg-blue-100 text-blue-700"}`}
          >
            <Boxes size={15} />
          </div>
          <span
            className="max-w-[150px] truncate text-xs font-bold"
            title={label}
          >
            {label}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-3 divide-x divide-slate-100 px-2 py-2.5 text-center">
        <div>
          <p className="text-[10px] text-slate-400">IN</p>
          <p className="mt-0.5 text-sm font-bold text-slate-700">{incoming}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-400">OUT</p>
          <p className="mt-0.5 text-sm font-bold text-slate-700">{outgoing}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-400">COUPLING</p>
          <p
            className={`mt-0.5 text-sm font-bold ${coupling >= 4 ? "text-amber-600" : "text-slate-700"}`}
          >
            {coupling ?? "—"}
          </p>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2.5 !w-2.5 !border-2 !border-white !bg-blue-500"
      />
    </div>
  );
}

const nodeTypes = { packageNode: PackageNode };

const Dependencies = () => {
  const { selectedRepository, analysisResults, analyzing, analysisError } =
    useRepository();
  const [search, setSearch] = useState("");
  const [selectedPackage, setSelectedPackage] = useState("");
  const [view, setView] = useState("map");

  const structure = Array.isArray(analysisResults?.structure)
    ? analysisResults.structure
    : [];
  const dependencies = Array.isArray(analysisResults?.dependencies)
    ? analysisResults.dependencies
    : [];
  const architecture = Array.isArray(analysisResults?.architecture)
    ? analysisResults.architecture
    : [];
  const findings = Array.isArray(analysisResults?.architecture_findings)
    ? analysisResults.architecture_findings
    : [];
  const hasAnalysis = Boolean(analysisResults);
  const repositoryName =
    selectedRepository?.name ||
    selectedRepository?.repository_name ||
    selectedRepository?.url ||
    "No repository selected";

  const packageNames = useMemo(
    () => [
      ...new Set(
        structure
          .map((row) => String(row.package_path ?? "").trim())
          .filter(Boolean),
      ),
    ],
    [structure],
  );
  const acceptedEdges = useMemo(() => {
    const known = new Set(packageNames);
    const seen = new Set();
    return dependencies.flatMap((row) => {
      const source = String(row.source_package ?? "").trim();
      const target = String(row.target_package ?? "").trim();
      if (
        !source ||
        !target ||
        source === target ||
        !known.has(source) ||
        !known.has(target)
      )
        return [];
      const id = `${source}→${target}`;
      if (seen.has(id)) return [];
      seen.add(id);
      return [{ id, source, target }];
    });
  }, [dependencies, packageNames]);

  const architectureByPackage = useMemo(
    () =>
      new Map(architecture.map((row) => [String(row.package_path ?? ""), row])),
    [architecture],
  );
  const incomingByPackage = useMemo(() => {
    const result = new Map(packageNames.map((name) => [name, 0]));
    acceptedEdges.forEach((edge) =>
      result.set(edge.target, (result.get(edge.target) || 0) + 1),
    );
    return result;
  }, [acceptedEdges, packageNames]);
  const outgoingByPackage = useMemo(() => {
    const result = new Map(packageNames.map((name) => [name, 0]));
    acceptedEdges.forEach((edge) =>
      result.set(edge.source, (result.get(edge.source) || 0) + 1),
    );
    return result;
  }, [acceptedEdges, packageNames]);

  const filteredPackages = packageNames.filter((name) =>
    name.toLowerCase().includes(search.toLowerCase()),
  );
  const visiblePackages = filteredPackages.length ? filteredPackages : [];
  const chosenPackage = packageNames.includes(selectedPackage)
    ? selectedPackage
    : visiblePackages[0] || "";
  const chosenArchitecture = architectureByPackage.get(chosenPackage);
  const incoming = acceptedEdges.filter(
    (edge) => edge.target === chosenPackage,
  );
  const outgoing = acceptedEdges.filter(
    (edge) => edge.source === chosenPackage,
  );
  const cycleFindings = findings.filter(
    (item) =>
      String(item.finding_type ?? "").toUpperCase() === "CIRCULAR_DEPENDENCY",
  );
  const highCoupling = architecture.filter(
    (row) => Number(row.total_coupling ?? 0) >= 4,
  );
  const connected = new Set(
    acceptedEdges.flatMap((edge) => [edge.source, edge.target]),
  );
  const isolatedCount = packageNames.filter(
    (name) => !connected.has(name),
  ).length;

  const nodes = useMemo(() => {
    const names = packageNames.filter((name) =>
      name.toLowerCase().includes(search.toLowerCase()),
    );
    const columns = Math.max(1, Math.ceil(Math.sqrt(names.length)));
    return names.map((name, index) => {
      const row = architectureByPackage.get(name);
      return {
        id: name,
        type: "packageNode",
        position: {
          x: (index % columns) * 270,
          y: Math.floor(index / columns) * 190,
        },
        data: {
          label: name,
          incoming: incomingByPackage.get(name) || 0,
          outgoing: outgoingByPackage.get(name) || 0,
          coupling: row?.total_coupling,
          selected: name === chosenPackage,
        },
        selected: name === chosenPackage,
      };
    });
  }, [
    packageNames,
    search,
    architectureByPackage,
    incomingByPackage,
    outgoingByPackage,
    chosenPackage,
  ]);

  const edges = useMemo(
    () =>
      acceptedEdges
        .filter(
          (edge) =>
            nodes.some((node) => node.id === edge.source) &&
            nodes.some((node) => node.id === edge.target),
        )
        .map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: "smoothstep",
          animated:
            edge.source === chosenPackage || edge.target === chosenPackage,
          style: {
            stroke:
              edge.source === chosenPackage || edge.target === chosenPackage
                ? "#2563eb"
                : "#94a3b8",
            strokeWidth:
              edge.source === chosenPackage || edge.target === chosenPackage
                ? 2.5
                : 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color:
              edge.source === chosenPackage || edge.target === chosenPackage
                ? "#2563eb"
                : "#94a3b8",
            width: 16,
            height: 16,
          },
          label:
            edge.source === chosenPackage || edge.target === chosenPackage
              ? "depends on"
              : undefined,
          labelStyle: { fill: "#475569", fontSize: 10, fontWeight: 600 },
          labelBgStyle: { fill: "#ffffff", fillOpacity: 0.9 },
        })),
    [acceptedEdges, nodes, chosenPackage],
  );

  const stats = [
    {
      label: "Structural packages",
      value: packageNames.length,
      note: "Packages detected by analyzer",
      icon: Boxes,
      tone: "blue",
    },
    {
      label: "Accepted dependencies",
      value: acceptedEdges.length,
      note: "Unique internal package edges",
      icon: GitBranch,
      tone: "violet",
    },
    {
      label: "High-coupling candidates",
      value: highCoupling.length,
      note: "Coupling ≥ 4; review suggested",
      icon: ShieldAlert,
      tone: "amber",
    },
    {
      label: "Isolated packages",
      value: isolatedCount,
      note: "No accepted edge in this graph",
      icon: Unplug,
      tone: "slate",
    },
  ];

  return (
    <main className="min-h-full space-y-5 bg-slate-50/70 p-1 sm:p-2">
      <header className="relative overflow-hidden rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-blue-100/70 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 p-3.5 text-white shadow-lg shadow-blue-600/20">
              <Workflow size={25} />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
                  Dependency Intelligence
                </h1>
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-blue-700">
                  Repository agent
                </span>
              </div>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Investigate package relationships, inspect dependency paths, and
                review architecture-analysis signals in one workspace.
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <span className="inline-flex max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-600">
                  <Database size={13} className="shrink-0 text-slate-400" />
                  <span className="truncate font-medium text-slate-800">
                    {repositoryName}
                  </span>
                </span>
                <span
                  className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-semibold ${analyzing ? "bg-amber-50 text-amber-700" : hasAnalysis ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${analyzing ? "animate-pulse bg-amber-500" : hasAnalysis ? "bg-emerald-500" : "bg-slate-400"}`}
                  />
                  {analyzing
                    ? "Analysis running"
                    : hasAnalysis
                      ? "Analysis data loaded"
                      : "Awaiting analysis"}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 xl:self-center">
            <span
              className={`h-2 w-2 rounded-full ${analyzing ? "animate-pulse bg-amber-500" : "bg-emerald-500"}`}
            />
            {analyzing
              ? "Updating analysis…"
              : "Using latest available results"}
          </div>
        </div>
      </header>

      {analysisError && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
        >
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Repository analysis issue</p>
            <p className="mt-1 break-words">{String(analysisError)}</p>
          </div>
        </div>
      )}

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <Stat key={stat.label} {...stat} />
        ))}
      </section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Architecture workspace
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Select a package to trace its incoming and outgoing relationships.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="relative block">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Find a package…"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-50 sm:w-64"
              />
            </label>
            <div className="flex rounded-xl border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                onClick={() => setView("map")}
                className={`rounded-lg px-3 py-2 text-xs font-semibold ${view === "map" ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"}`}
              >
                Map view
              </button>
              <button
                type="button"
                onClick={() => setView("list")}
                className={`rounded-lg px-3 py-2 text-xs font-semibold ${view === "list" ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"}`}
              >
                List view
              </button>
            </div>
          </div>
        </div>

        {!hasAnalysis ? (
          <div className="m-5 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
            <Workflow size={28} className="mx-auto text-slate-300" />
            <h3 className="mt-3 font-semibold text-slate-700">
              No repository analysis yet
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Select a repository and run the analysis to populate this
              workspace.
            </p>
          </div>
        ) : view === "map" ? (
          <div className="grid min-w-0 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_310px]">
            <div className="min-w-0 border-b border-slate-100 xl:border-b-0 xl:border-r">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/70 px-4 py-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <span className="h-2 w-2 rounded-full bg-blue-500" />
                  Package relationship map
                </div>
                <span className="text-[11px] text-slate-400">
                  {nodes.length} visible packages · {edges.length} visible edges
                </span>
              </div>
              <div className="h-[520px] w-full bg-slate-50/40">
                {nodes.length ? (
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    onNodeClick={(_, node) => setSelectedPackage(node.id)}
                    fitView
                    fitViewOptions={{ padding: 0.22 }}
                    minZoom={0.2}
                    maxZoom={1.7}
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background color="#cbd5e1" gap={22} size={1} />
                    <Controls position="bottom-left" />
                    <MiniMap
                      position="bottom-right"
                      pannable
                      zoomable
                      nodeColor={(node) =>
                        node.id === chosenPackage ? "#2563eb" : "#93c5fd"
                      }
                      maskColor="rgba(241,245,249,0.65)"
                    />
                  </ReactFlow>
                ) : (
                  <div className="flex h-full items-center justify-center p-8 text-center text-sm text-slate-500">
                    No packages match “{search}”. Try a different search.
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-2 border-t border-slate-100 px-4 py-3 text-[11px] text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-blue-600" />
                  Selected package
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-slate-400" />
                  Dependency direction: source → target
                </span>
                <span>Scroll to zoom · Drag to pan</span>
              </div>
            </div>
            <aside className="min-w-0 p-4 sm:p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-blue-600">
                    Package inspector
                  </p>
                  <h3 className="mt-1 break-all text-base font-bold text-slate-900">
                    {chosenPackage || "Select a package"}
                  </h3>
                </div>
                {chosenPackage && (
                  <button
                    type="button"
                    onClick={() => setSelectedPackage("")}
                    title="Clear selection"
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
              {chosenPackage ? (
                <>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <div className="rounded-xl bg-blue-50 p-3">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-blue-700">
                        <ArrowDownRight size={13} />
                        Incoming
                      </div>
                      <p className="mt-1 text-xl font-bold text-blue-950">
                        {incoming.length}
                      </p>
                    </div>
                    <div className="rounded-xl bg-violet-50 p-3">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-violet-700">
                        <ArrowUpRight size={13} />
                        Outgoing
                      </div>
                      <p className="mt-1 text-xl font-bold text-violet-950">
                        {outgoing.length}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <p className="mb-2 text-xs font-bold text-slate-700">
                      Incoming dependencies
                    </p>
                    <div className="space-y-1.5">
                      {incoming.slice(0, 5).map((edge) => (
                        <button
                          key={edge.id}
                          type="button"
                          onClick={() => setSelectedPackage(edge.source)}
                          className="flex w-full items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-2 text-left text-xs text-slate-600 hover:border-blue-200 hover:bg-blue-50"
                        >
                          <ArrowDownRight
                            size={13}
                            className="shrink-0 text-blue-500"
                          />
                          <span className="break-all">{edge.source}</span>
                        </button>
                      ))}
                      {!incoming.length && (
                        <p className="rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-400">
                          No incoming accepted edges.
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="mt-4">
                    <p className="mb-2 text-xs font-bold text-slate-700">
                      Outgoing dependencies
                    </p>
                    <div className="space-y-1.5">
                      {outgoing.slice(0, 5).map((edge) => (
                        <button
                          key={edge.id}
                          type="button"
                          onClick={() => setSelectedPackage(edge.target)}
                          className="flex w-full items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-2 text-left text-xs text-slate-600 hover:border-blue-200 hover:bg-blue-50"
                        >
                          <ArrowUpRight
                            size={13}
                            className="shrink-0 text-violet-500"
                          />
                          <span className="break-all">{edge.target}</span>
                        </button>
                      ))}
                      {!outgoing.length && (
                        <p className="rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-400">
                          No outgoing accepted edges.
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="mt-4 rounded-xl border border-slate-200 p-3">
                    <p className="text-xs font-bold text-slate-700">
                      Architecture metrics
                    </p>
                    <div className="mt-2 space-y-2 text-xs">
                      <div className="flex justify-between gap-3">
                        <span className="text-slate-500">Total coupling</span>
                        <span className="font-semibold text-slate-800">
                          {chosenArchitecture?.total_coupling ??
                            "Not available"}
                        </span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="text-slate-500">Package files</span>
                        <span className="font-semibold text-slate-800">
                          {chosenArchitecture?.file_count ??
                            chosenArchitecture?.files_count ??
                            "Not available"}
                        </span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p className="mt-4 rounded-xl border border-dashed border-slate-200 p-4 text-xs leading-5 text-slate-400">
                  Choose a node on the map to inspect its relationships and
                  available metrics.
                </p>
              )}
            </aside>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">Package</th>
                  <th className="px-5 py-3 font-semibold">Incoming</th>
                  <th className="px-5 py-3 font-semibold">Outgoing</th>
                  <th className="px-5 py-3 font-semibold">Coupling</th>
                  <th className="px-5 py-3 font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visiblePackages.map((name) => (
                  <tr key={name} className="hover:bg-slate-50">
                    <td className="max-w-sm break-all px-5 py-3 font-medium text-slate-800">
                      {name}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {incomingByPackage.get(name) || 0}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {outgoingByPackage.get(name) || 0}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {architectureByPackage.get(name)?.total_coupling ?? "—"}
                    </td>
                    <td className="px-5 py-3">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPackage(name);
                          setView("map");
                        }}
                        className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
                {!visiblePackages.length && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-5 py-10 text-center text-sm text-slate-400"
                    >
                      No packages match this search.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <CircularDependencyCard findings={cycleFindings} />
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-amber-50 p-2.5 text-amber-700">
              <ShieldAlert size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">
                Coupling review queue{" "}
                <span className="ml-1 font-normal text-slate-400">
                  ({highCoupling.length})
                </span>
              </h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Packages with total coupling of 4 or more, based on the current
                architecture metrics.
              </p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {highCoupling.slice(0, 5).map((row) => (
              <button
                key={row.package_path}
                type="button"
                onClick={() => {
                  setSelectedPackage(row.package_path);
                  setSearch("");
                  setView("map");
                }}
                className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2.5 text-left hover:border-amber-200 hover:bg-amber-50/50"
              >
                <span className="break-all text-xs font-semibold text-slate-700">
                  {row.package_path}
                </span>
                <span className="shrink-0 rounded-lg bg-amber-100 px-2 py-1 text-xs font-bold text-amber-800">
                  {row.total_coupling}
                </span>
              </button>
            ))}
            {!highCoupling.length && (
              <p className="rounded-xl border border-dashed border-slate-200 px-3 py-5 text-center text-xs text-slate-400">
                No packages meet this coupling threshold in the current results.
              </p>
            )}
          </div>
        </div>
      </section>

      <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs leading-5 text-slate-500">
        <Link2 size={15} className="mt-0.5 shrink-0 text-slate-400" />
        <p>
          <span className="font-semibold text-slate-700">Data note:</span>{" "}
          Counts and relationships are derived from the current analyzer output.
          “Isolated” means no accepted internal edge appears in this graph; it
          does not prove the package is unused. Coupling thresholds are review
          signals, not confirmed defects. No dependency-health score is
          inferred.
        </p>
      </div>
    </main>
  );
};

export default Dependencies;
