import React from 'react';
import { ArrowRight, Circle } from 'lucide-react';
import SectionHeader from './SectionHeader';
import GraphStats from './GraphStats';

const graphNodes = [
  {
    label: 'Requirement',
    value: '2,556',
    x: 65,
    y: 55,
  },
  {
    label: 'Component',
    value: '3,142',
    x: 205,
    y: 55,
  },
  {
    label: 'Test Case',
    value: '1,786',
    x: 275,
    y: 150,
  },
  {
    label: 'User Story',
    value: '834',
    x: 55,
    y: 170,
  },
  {
    label: 'Document',
    value: '12,346',
    x: 90,
    y: 260,
  },
  {
    label: 'Defect',
    value: '1,024',
    x: 220,
    y: 260,
  },
  {
    label: 'Code File',
    value: '6,891',
    x: 290,
    y: 205,
  },
];

const KnowledgeGraphCard = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">

      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">

        <h2 className="text-sm font-semibold text-slate-900">
          SKG (Software Knowledge Graph)
        </h2>

        <button className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
          Explore Graph
          <ArrowRight size={13} />
        </button>

      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_180px]">

        {/* Graph */}
        <div className="relative min-h-[430px] overflow-hidden p-4">

          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 350 330"
            preserveAspectRatio="xMidYMid meet"
          >

            {graphNodes.map((node) => (
              <line
                key={`line-${node.label}`}
                x1="175"
                y1="165"
                x2={node.x}
                y2={node.y}
                stroke={
                  node.label === 'Defect' ||
                  node.label === 'Code File'
                    ? '#F87171'
                    : '#CBD5E1'
                }
                strokeWidth="1.5"
                strokeDasharray={
                  node.label === 'Defect'
                    ? '5 4'
                    : undefined
                }
              />
            ))}

          </svg>

          {/* Center */}
          <div
            className="
              absolute left-1/2 top-1/2
              flex h-24 w-24
              -translate-x-1/2
              -translate-y-1/2
              flex-col
              items-center justify-center
              rounded-full
              bg-indigo-600
              text-white
              shadow-xl
              shadow-indigo-600/20
            "
          >
            <span className="text-[11px]">
              Project
            </span>

            <strong className="text-base">
              1,248
            </strong>
          </div>

          {/* Nodes */}
          {graphNodes.map((node) => (
            <div
              key={node.label}
              className="
                absolute
                -translate-x-1/2
                -translate-y-1/2
              "
              style={{
                left: `${(node.x / 350) * 100}%`,
                top: `${(node.y / 330) * 100}%`,
              }}
            >
              <div className="flex items-center gap-1.5">
                <span className="h-5 w-5 rounded-full bg-blue-600 ring-4 ring-blue-50" />

                <div className="whitespace-nowrap">
                  <p className="text-[9px] font-semibold text-slate-700">
                    {node.label}
                  </p>

                  <p className="text-[9px] text-slate-500">
                    {node.value}
                  </p>
                </div>
              </div>
            </div>
          ))}

          {/* Legend */}
          <div className="absolute bottom-4 left-5 flex flex-wrap gap-4 text-[9px] text-slate-500">

            <span className="flex items-center gap-1">
              <Circle size={8} fill="#4338CA" />
              Node
            </span>

            <span className="flex items-center gap-1">
              <span className="h-px w-6 bg-slate-400" />
              Relationship
            </span>

            <span className="flex items-center gap-1">
              <span className="w-6 border-t border-dashed border-red-500" />
              Problematic
            </span>

          </div>

        </div>

        {/* Graph Stats */}
        <GraphStats />

      </div>
    </section>
  );
};

export default KnowledgeGraphCard;