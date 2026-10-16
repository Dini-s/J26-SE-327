import React, { useCallback, useMemo, useState } from "react";

import { Background, Controls, MiniMap, ReactFlow } from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import ArchitectureNode from "./ArchitectureNode";

import {
  architectureEdges,
  architectureNodes,
} from "../../../data/architectureData";

const ArchitectureGraph = ({ onSelectModule }) => {
  const nodeTypes = useMemo(
    () => ({
      architecture: ArchitectureNode,
    }),
    [],
  );

  const [nodes] = useState(
    architectureNodes.map((node) => ({
      id: node.id,
      type: "architecture",
      position: node.position,
      data: node,
    })),
  );

  const [edges] = useState(
    architectureEdges.map((edge) => ({
      ...edge,

      animated: edge.violation === true,

      style: edge.violation
        ? {
            stroke: "#ef4444",
            strokeWidth: 1.5,
            strokeDasharray: "5 4",
          }
        : {
            stroke: "#64748b",
            strokeWidth: 1,
          },

      markerEnd: {
        type: "arrowclosed",
        color: edge.violation ? "#ef4444" : "#64748b",
      },
    })),
  );

  const handleNodeClick = useCallback(
    (_, node) => {
      onSelectModule(node.data);
    },
    [onSelectModule],
  );

  return (
    <div className="h-[470px] w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{
          padding: 0.15,
        }}
        minZoom={0.4}
        maxZoom={1.6}
        proOptions={{
          hideAttribution: true,
        }}
      >
        <Background gap={20} size={1} color="#f1f5f9" />

        <Controls
          showInteractive={false}
          className="!rounded-lg !border !border-slate-200 !bg-white !shadow-sm"
        />

        <MiniMap
          nodeColor={(node) => {
            if (node.data.layer === "Presentation") {
              return "#3b82f6";
            }

            if (node.data.layer === "Service") {
              return "#10b981";
            }

            if (node.data.layer === "Repository") {
              return "#8b5cf6";
            }

            if (node.data.layer === "Infrastructure") {
              return "#f97316";
            }

            return "#94a3b8";
          }}
          className="!rounded-lg !border !border-slate-200"
        />
      </ReactFlow>
    </div>
  );
};

export default ArchitectureGraph;
