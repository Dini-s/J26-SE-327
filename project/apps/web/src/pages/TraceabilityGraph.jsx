import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useApi, useProject } from "../api/c4";
import { Card, TraceHeader } from "../component/traceability/common";
import { GraphView, MatrixView, NodeDetails } from "../component/traceability/GraphView";
import { useVisible } from "../component/traceability/useVisible";

const Toggle = ({ checked, onChange, children }) => (
  <label className="flex cursor-pointer items-center gap-1.5 text-[12px] text-slate-600">
    <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="accent-indigo-600" />
    {children}
  </label>
);

const TraceabilityGraph = () => {
  const { project, error: projectsError } = useProject();
  const links = useApi(project ? `/api/links?project=${encodeURIComponent(project)}` : null);

  const [tab, setTab] = useState("graph");
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ verified: true, decayed: true, orphans: true, minConfidence: 0, search: "" });
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
        title="Traceability Graph"
        subtitle="Requirements on the left, the code that implements them on the right. Every line is a link the LLM verified; red dashed lines have decayed."
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
          <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg bg-slate-50 px-3 py-2.5">
            <Toggle checked={filters.verified} onChange={(v) => set({ verified: v })}>verified</Toggle>
            <Toggle checked={filters.decayed} onChange={(v) => set({ decayed: v })}>decayed</Toggle>
            <Toggle checked={filters.orphans} onChange={(v) => set({ orphans: v })}>orphan requirements</Toggle>
            <label className="flex items-center gap-2 text-[12px] text-slate-600">
              min confidence {filters.minConfidence.toFixed(2)}
              <input type="range" min="0" max="1" step="0.05" value={filters.minConfidence} onChange={(event) => set({ minConfidence: Number(event.target.value) })} className="w-28 accent-indigo-600" />
            </label>
            <div className="ml-auto flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-[12px] text-slate-500">
              <Search size={13} />
              <input value={filters.search} onChange={(event) => set({ search: event.target.value })} placeholder="find a node" className="w-32 bg-transparent outline-none placeholder:text-slate-400" />
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

        <Card title="Details" subtitle="Click a node in the graph or a requirement in the matrix">
          <NodeDetails selected={selected} links={all} orphans={orphans} requirementText={requirementText} />
        </Card>
      </div>
    </div>
  );
};

export default TraceabilityGraph;
