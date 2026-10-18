import  { useCallback } from "react";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  Handle,
  Position,
} from "@xyflow/react";

import { Database, Globe, Layers, Package, Settings } from "lucide-react";

const nodeStyles = {
  presentation: {
    border: "border-blue-300",
    bg: "bg-blue-50",
    icon: "text-blue-600",
    Icon: Globe,
  },

  service: {
    border: "border-emerald-300",
    bg: "bg-emerald-50",
    icon: "text-emerald-600",
    Icon: Layers,
  },

  repository: {
    border: "border-purple-300",
    bg: "bg-purple-50",
    icon: "text-purple-600",
    Icon: Package,
  },

  infrastructure: {
    border: "border-orange-300",
    bg: "bg-orange-50",
    icon: "text-orange-600",
    Icon: Settings,
  },

  external: {
    border: "border-slate-300",
    bg: "bg-slate-50",
    icon: "text-slate-500",
    Icon: Database,
  },
};

const ModuleNode = ({ data }) => {
  const style = nodeStyles[data.type] || nodeStyles.external;

  const Icon = style.Icon;

  return (
    <div
      className={`
        relative
        w-[150px]
        rounded-lg
        border
        ${style.border}
        ${style.bg}
        p-2.5
        shadow-sm
        transition-all
        ${data.selected ? "ring-2 ring-red-300 shadow-md" : "hover:shadow-md"}
      `}
    >
      {/* Target */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />

      <div className="flex items-center gap-2">
        <div
          className={`
            flex
            h-7
            w-7
            shrink-0
            items-center
            justify-center
            rounded-md
            bg-white
            ${style.icon}
          `}
        >
          <Icon size={14} />
        </div>

        <div className="min-w-0">
          <p className="truncate text-[11px] font-bold text-slate-800">
            {data.label}
          </p>

          <p className="truncate text-[11px] text-slate-400">{data.package}</p>
        </div>
      </div>

      <p className="mt-1 text-[11px]">
        Risk:{" "}
        <span
          className={
            data.risk === "High"
              ? "font-semibold text-red-500"
              : data.risk === "Medium"
                ? "font-semibold text-orange-500"
                : "font-semibold text-emerald-600"
          }
        >
          {data.risk}
        </span>
      </p>

      {/* Source */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0 !bg-slate-400"
      />
    </div>
  );
};

const nodeTypes = {
  module: ModuleNode,
};

const initialNodes = [
  {
    id: "web",
    type: "module",
    position: {
      x: 350,
      y: 20,
    },
    data: {
      label: "WebController",
      package: "com.petclinic.web",
      type: "presentation",
      risk: "Low",
    },
  },

  {
    id: "pet",
    type: "module",
    position: {
      x: 100,
      y: 150,
    },
    data: {
      label: "PetService",
      package: "com.petclinic.pet",
      type: "service",
      risk: "Medium",
    },
  },

  {
    id: "visit",
    type: "module",
    position: {
      x: 350,
      y: 150,
    },
    data: {
      label: "VisitService",
      package: "com.petclinic.visit",
      type: "service",
      risk: "Medium",
    },
  },

  {
    id: "owner",
    type: "module",
    position: {
      x: 600,
      y: 150,
    },
    data: {
      label: "OwnerService",
      package: "com.petclinic.owner",
      type: "service",
      risk: "High",
    },
  },

  {
    id: "petRepo",
    type: "module",
    position: {
      x: 100,
      y: 300,
    },
    data: {
      label: "PetRepository",
      package: "com.petclinic.repository",
      type: "repository",
      risk: "Low",
    },
  },

  {
    id: "visitRepo",
    type: "module",
    position: {
      x: 350,
      y: 300,
    },
    data: {
      label: "VisitRepository",
      package: "com.petclinic.repository",
      type: "repository",
      risk: "Medium",
    },
  },

  {
    id: "ownerRepo",
    type: "module",
    position: {
      x: 600,
      y: 300,
    },
    data: {
      label: "OwnerRepository",
      package: "com.petclinic.repository",
      type: "repository",
      risk: "Medium",
    },
  },

  {
    id: "database",
    type: "module",
    position: {
      x: 100,
      y: 450,
    },
    data: {
      label: "DataSource",
      package: "org.springframework.jdbc",
      type: "infrastructure",
      risk: "Low",
    },
  },

  {
    id: "transaction",
    type: "module",
    position: {
      x: 350,
      y: 450,
    },
    data: {
      label: "TransactionManager",
      package: "org.springframework.tx",
      type: "infrastructure",
      risk: "Low",
    },
  },

  {
    id: "cache",
    type: "module",
    position: {
      x: 600,
      y: 450,
    },
    data: {
      label: "CacheManager",
      package: "org.springframework.cache",
      type: "infrastructure",
      risk: "Low",
    },
  },
];

const initialEdges = [
  // Web → Services
  {
    id: "web-pet",
    source: "web",
    target: "pet",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  {
    id: "web-visit",
    source: "web",
    target: "visit",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  {
    id: "web-owner",
    source: "web",
    target: "owner",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  // Services → Repositories
  {
    id: "pet-repository",
    source: "pet",
    target: "petRepo",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  {
    id: "visit-repository",
    source: "visit",
    target: "visitRepo",
    type: "smoothstep",
    markerEnd: {
      type: "smoothstep",
    },
  },

  {
    id: "owner-repository",
    source: "owner",
    target: "ownerRepo",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },

    style: {
      stroke: "#ef4444",
      strokeWidth: 2,
    },
  },

  // Repository → Infrastructure
  {
    id: "repo-db",
    source: "petRepo",
    target: "database",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  {
    id: "repo-transaction",
    source: "visitRepo",
    target: "transaction",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  {
    id: "repo-cache",
    source: "ownerRepo",
    target: "cache",
    type: "smoothstep",
    markerEnd: {
      type: "arrowclosed",
    },
  },

  // Circular dependency
  {
    id: "owner-visit",
    source: "owner",
    target: "visit",
    type: "smoothstep",

    animated: true,

    style: {
      stroke: "#ef4444",
      strokeWidth: 2,
      strokeDasharray: "5 4",
    },

    markerEnd: {
      type: "arrowclosed",
      color: "#ef4444",
    },
  },
];

const DependencyGraph = ({ onNodeSelect }) => {
  const handleNodeClick = useCallback(
    (_, node) => {
      onNodeSelect?.(node);
    },
    [onNodeSelect],
  );

  return (
    <div className="relative h-[390px] w-full">
      <ReactFlow
        nodes={initialNodes}
        edges={initialEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{
          padding: 0.2,
        }}
        minZoom={0.4}
        maxZoom={2}
        proOptions={{
          hideAttribution: true,
        }}
      >
        <Background gap={18} size={1} color="#cbd5e1" />

        <Controls />

        <MiniMap />
      </ReactFlow>
    </div>
  );
};

export default DependencyGraph;
