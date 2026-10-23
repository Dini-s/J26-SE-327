import { useCallback, useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";
import { Database, Layers, Package } from "lucide-react";

const nodeStyles = {
  package: {
    border: "border-blue-300",
    bg: "bg-blue-50",
    icon: "text-blue-600",
    Icon: Package,
  },
  connected: {
    border: "border-emerald-300",
    bg: "bg-emerald-50",
    icon: "text-emerald-600",
    Icon: Layers,
  },
  external: {
    border: "border-slate-300",
    bg: "bg-slate-50",
    icon: "text-slate-500",
    Icon: Database,
  },
};

const ModuleNode = ({ data }) => {
  const style = nodeStyles[data.kind] || nodeStyles.package;
  const Icon = style.Icon;
  return (
    <div
      className={`relative w-[210px] rounded-lg border ${style.border} ${style.bg} p-2.5 shadow-sm ${data.selected ? "ring-2 ring-blue-400" : ""}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />
      <div className="flex items-center gap-2">
        <div
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white ${style.icon}`}
        >
          <Icon size={14} />
        </div>
        <div className="min-w-0">
          <p
            title={data.label}
            className="break-all text-[11px] font-bold text-slate-800"
          >
            {data.label}
          </p>
          <p className="mt-1 text-[10px] text-slate-500">
            Coupling: {data.coupling ?? "—"}
          </p>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />
    </div>
  );
};
const nodeTypes = { module: ModuleNode };

const DependencyGraph = ({
  packages = [],
  edges = [],
  metricsByPackage = new Map(),
  onNodeSelect,
  selectedPackage,
}) => {
  const nodes = useMemo(() => {
    const columns = 3;
    return packages.map((pkg, index) => {
      const packagePath = pkg.package_path;
      const metric = metricsByPackage.get(packagePath) || {};
      return {
        id: packagePath,
        type: "module",
        position: {
          x: (index % columns) * 270 + 30,
          y: Math.floor(index / columns) * 150 + 30,
        },
        data: {
          label: packagePath,
          package: packagePath,
          kind: "package",
          coupling: metric.total_coupling ?? "—",
          selected: selectedPackage === packagePath,
        },
      };
    });
  }, [packages, metricsByPackage, selectedPackage]);

  const visibleIds = useMemo(
    () => new Set(nodes.map((node) => node.id)),
    [nodes],
  );
  const flowEdges = useMemo(
    () =>
      edges
        .filter(
          (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
        )
        .map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: "smoothstep",
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: "#64748b", strokeWidth: 1.6 },
        })),
    [edges, visibleIds],
  );
  const handleNodeClick = useCallback(
    (_, node) => onNodeSelect?.(node),
    [onNodeSelect],
  );

  if (!packages.length)
    return (
      <div className="flex h-[390px] items-center justify-center p-6 text-center text-sm text-slate-500">
        No structural packages are available for the current analysis.
      </div>
    );

  return (
    <div className="relative h-[430px] w-full">
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.25}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={18} size={1} color="#cbd5e1" />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
};
export default DependencyGraph;
