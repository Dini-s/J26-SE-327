
import { useCallback, useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import ArchitectureNode from "./ArchitectureNode";

const ArchitectureGraph = ({ nodes = [], edges = [], onSelectModule }) => {
  const nodeTypes = useMemo(
    () => ({ architecture: ArchitectureNode }),
    [],
  );

  const graphEdges = useMemo(
    () =>
      edges.map((edge) => {
        const isViolation = edge.violation === true;

        return {
          ...edge,
          animated: isViolation,
          style: {
            stroke: isViolation ? "#ef4444" : "#94a3b8",
            strokeWidth: isViolation ? 1.5 : 1,
            ...(isViolation ? { strokeDasharray: "5 4" } : {}),
          },
          markerEnd: {
            type: "arrowclosed",
            color: isViolation ? "#ef4444" : "#94a3b8",
          },
        };
      }),
    [edges],
  );

  const handleNodeClick = useCallback(
    (_, node) => onSelectModule?.(node.data),
    [onSelectModule],
  );

  return (
    <div className="h-[470px] w-full">
      {nodes.length === 0 ? (
        <div className="flex h-full items-center justify-center p-6 text-center">
          <div>
            <p className="text-sm font-semibold text-slate-700">
              No architecture data available
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Select a repository and run its analysis to populate the graph.
            </p>
          </div>
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={graphEdges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          minZoom={0.4}
          maxZoom={1.6}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} color="#f1f5f9" />
          <Controls
            showInteractive={false}
            className="!rounded-lg !border !border-slate-200 !bg-white !shadow-sm"
          />
          <MiniMap
            nodeColor={(node) => {
              switch (node.data?.layer) {
                case "Presentation":
                  return "#3b82f6";
                case "Service":
                  return "#10b981";
                case "Repository":
                  return "#8b5cf6";
                case "Infrastructure":
                  return "#f97316";
                default:
                  return "#94a3b8";
              }
            }}
            className="!rounded-lg !border !border-slate-200"
          />
        </ReactFlow>
      )}
    </div>
  );
};

export default ArchitectureGraph;
