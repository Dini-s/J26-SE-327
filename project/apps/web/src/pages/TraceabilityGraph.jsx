import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useApi, useProject } from "../api/c4";
import { Card, TraceHeader } from "../component/traceability/common";
import { GraphView, MatrixView, NodeDetails } from "../component/traceability/GraphView";
import { useVisible } from "../component/traceability/useVisible";

const STATUS_FILTERS = [
  ["verified", "Approved", "#10b981"],
  ["pending_review", "Needs review", "#f59e0b"],
  ["deferred", "Deferred", "#0ea5e9"],
  ["rejected", "Rejected", "#94a3b8"],
  ["decayed", "Broken", "#ef4444"],
  ["orphans", "Orphan requirements", "#6366f1"],
];

const FilterChip = ({ checked, onChange, color, children }) => (
  <label className="c4-filter-chip" style={{ "--chip": color }}>
    <input type="checkbox" className="sr-only" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    <span className="c4-filter-dot" />
    {children}
  </label>
);

const TraceabilityGraph = () => {
  const { project, error: projectsError } = useProject();
  const links = useApi(project ? `/api/links?project=${encodeURIComponent(project)}` : null);

  const [tab, setTab] = useState("graph");
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ verified: true, decayed: true, pending_review: true, deferred: true, rejected: true, orphans: true, minConfidence: 0, search: "" });
  const set = (patch) => setFilters((previous) => ({ ...previous, ...patch }));

  const all = useMemo(() => links.data?.links ?? [], [links.data]);
  const orphans = useMemo(() => links.data?.orphans ?? [], [links.data]);
  const data = useVisible(all, orphans, filters);

  const requirementText = useMemo(() => {
    const map = new Map();
    all.forEach((l) => map.set(l.requirement, l.requirementText));
    orphans.forEach((o) => map.set(o.requirement, o.requirementText));
    return map;
  }, [all, orphans]);

  return (
    <div className="mx-auto w-full max-w-[1500px]">
      <TraceHeader
        title="Traceability graph"
        subtitle="Explore requirements and their connections to code."
        apiError={projectsError || links.error}
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card
          title={tab === "graph" ? "Trace graph" : "Traceability matrix"}
          subtitle={`${data.visible.length} links shown, ${data.reqs.length} requirements, ${data.codes.length} code files`}
          action={
            <div className="flex rounded-lg border border-slate-200 p-0.5 text-[12px]">
              {["graph", "matrix"].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`rounded-md px-3 py-1 font-medium capitalize ${tab === t ? "bg-indigo-600 text-white" : "text-slate-500 hover:text-indigo-600"}`}
                >
                  {t}
                </button>
              ))}
            </div>
          }
        >
          <div className="c4-filters">
            <div className="c4-filter-group" role="group" aria-label="Show links by status">
              {STATUS_FILTERS.map(([key, label, color]) => (
                <FilterChip key={key} color={color} checked={filters[key]} onChange={(value) => set({ [key]: value })}>{label}</FilterChip>
              ))}
            </div>
            <div className="c4-filter-tools">
              <label className="c4-slider">
                <span>Min confidence <b>{filters.minConfidence.toFixed(2)}</b></span>
                <input type="range" min="0" max="1" step="0.05" value={filters.minConfidence} onChange={(event) => set({ minConfidence: Number(event.target.value) })} aria-label="Minimum confidence" />
              </label>
              <label className="c4-find">
                <Search size={14} />
                <input value={filters.search} onChange={(event) => set({ search: event.target.value })} placeholder="Find a node" aria-label="Find a node" />
              </label>
            </div>
          </div>

          {links.loading && !links.data ? (
            <p className="py-16 text-center text-[13px] text-slate-400">Loading links...</p>
          ) : tab === "graph" ? (
            <GraphView data={data} selected={selected} onSelect={setSelected} requirementText={requirementText} />
          ) : (
            <MatrixView data={data} selected={selected} onSelect={setSelected} requirementText={requirementText} />
          )}
        </Card>

        <div className="min-w-0 self-start xl:sticky xl:top-24">
          <Card title="Details" subtitle="Select a node to inspect.">
            <NodeDetails selected={selected} links={all} orphans={orphans} requirementText={requirementText} />
          </Card>
        </div>
      </div>
    </div>
  );
};

export default TraceabilityGraph;
