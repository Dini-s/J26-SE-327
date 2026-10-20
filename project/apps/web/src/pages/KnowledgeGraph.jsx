import { useMemo, useRef, useState } from "react";
import { useApi, useProject } from "../api/c4";
import Inspector from "../component/knowledge/Inspector";
import UskgGraph from "../component/knowledge/UskgGraph";
import { Card, TraceHeader } from "../component/traceability/common";

const MODES = [
  ["links", "Trace links"],
  ["code", "Code structure (C2)"],
  ["requirements", "Requirement details (C1)"],
  ["all", "Everything"],
];

const LEGEND = [
  ["Linked requirement", "#e0d58d"], ["Code file", "#b9d2a9"], ["Repository", "#4fa3f0"], ["Package / Document", "#5cc8a0"],
  ["Evolution / Criterion", "#f2c14e"], ["User story", "#f5a15a"], ["Technical task", "#a58be8"], ["Finding", "#f08187"], ["Risk", "#7fd0c8"],
];

const KnowledgeGraph = () => {
  const { project, error: projectsError } = useProject();
  const [mode, setMode] = useState("links");
  const [flags, setFlags] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [arrange, setArrange] = useState(0);
  const focusRef = useRef(null);

  const graph = useApi(project ? `/api/graph?project=${encodeURIComponent(project)}&mode=${mode}` : null);
  const data = graph.data;

  const { nodes, edges, stats } = useMemo(() => {
    if (!data) return { nodes: [], edges: [], stats: "-" };
    const links = data.edges.filter((e) => ["verified", "decayed", "pending_review", "deferred", "rejected"].includes(e.category));
    const linked = new Set(links.filter((e) => e.category === "verified").flatMap((e) => [e.from, e.to]));
    const kept = data.nodes
      .filter((n) => n.kind !== "decayflag" || flags)
      .map((n) => ({ ...n, orphan: n.kind === "requirement" && data.mode !== "requirements" && !linked.has(n.id) }));
    const ids = new Set(kept.map((n) => n.id));
    return {
      nodes: kept,
      edges: data.edges.filter((e) => ids.has(e.from) && ids.has(e.to)),
      stats: `${links.filter((e) => e.category === "verified").length} approved · ${links.filter((e) => e.category === "pending_review").length} need review · ${links.filter((e) => e.category === "deferred").length} deferred · ${links.filter((e) => e.category === "rejected").length} rejected · ${links.filter((e) => e.category === "decayed").length} broken`,
    };
  }, [data, flags]);

  const focusFirstMatch = () => {
    const q = search.trim().toLowerCase();
    if (!q) return;
    const hit = nodes.find((n) => `${n.label} ${n.text || ""} ${n.id}`.toLowerCase().includes(q));
    if (hit) {
      setSelected({ type: "node", id: hit.id });
      focusRef.current?.(hit.id);
    }
  };

  const selectEdgeOrNode = (value) => setSelected(value);

  return (
    <div className="mx-auto w-full max-w-[1500px]">
      <TraceHeader
        title="Unified Software Knowledge Graph"
        subtitle="The shared graph the four components write to. Trace candidates (C4) show approved, pending, rejected and broken connections between requirements (C1) and code (C2). Select a node or an edge to inspect it."
        apiError={projectsError || graph.error}
      />

      <Card
        title="Graph"
        subtitle={stats}
        action={
          <div className="flex flex-wrap items-center gap-2 text-[12px]">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && focusFirstMatch()}
              placeholder="Search graph, Enter to focus"
              className="w-52 rounded-lg border border-slate-200 px-2.5 py-1.5 outline-none focus:border-indigo-400"
            />
            <select value={mode} onChange={(event) => { setMode(event.target.value); setSelected(null); }} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 outline-none" aria-label="What to show">
              {MODES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-slate-600">
              <input type="checkbox" checked={flags} onChange={(event) => setFlags(event.target.checked)} className="accent-indigo-600" />
              Decay records
            </label>
            <button type="button" onClick={() => setArrange((value) => value + 1)} className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">Arrange</button>
          </div>
        }
      >
        <div className="-m-5 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px]">
          <UskgGraph className="h-[640px]" nodes={nodes} edges={edges} selected={selected} onSelect={selectEdgeOrNode} search={search} arrangeToken={arrange} focusRef={focusRef} />
          <div className="max-h-[640px] overflow-auto border-t border-slate-100 p-4 xl:border-l xl:border-t-0">
            <Inspector selected={selected} nodes={nodes} edges={edges} />
          </div>
        </div>
        <div className="-mx-5 -mb-5 mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 px-5 py-3 text-[12px] text-slate-600">
          {LEGEND.map(([label, color]) => (
            <span key={label} className="flex items-center gap-2"><i className="inline-block h-3 w-3 rounded-full" style={{ background: color }} />{label}</span>
          ))}
          <span className="flex items-center gap-2"><i className="inline-block h-3 w-3 rounded-full border border-dashed border-slate-400" />Unlinked requirement</span>
          <span className="flex items-center gap-2"><i className="inline-block h-0.5 w-6 bg-slate-400" />Verified link</span>
          <span className="flex items-center gap-2"><i className="inline-block w-6 border-t-2 border-dashed border-red-500" />Broken link</span>
        </div>
      </Card>
    </div>
  );
};

export default KnowledgeGraph;
