import { useMemo, useRef, useState } from "react";
import { AlertTriangle, Database, Search } from "lucide-react";
import { useApi, useProject } from "../api/c4";
import Inspector from "../component/knowledge/Inspector";
import UskgGraph from "../component/knowledge/UskgGraph";
import "../component/knowledge/knowledge.css";

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

const LINK_CATEGORIES = ["verified", "decayed", "pending_review", "deferred", "rejected"];
const STAT_CHIPS = [
  ["verified", "Approved", "#10b981"],
  ["pending_review", "Need review", "#f59e0b"],
  ["deferred", "Deferred", "#0ea5e9"],
  ["rejected", "Rejected", "#94a3b8"],
  ["decayed", "Broken", "#ef4444"],
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
  const apiError = projectsError || graph.error;

  const { nodes, edges, counts } = useMemo(() => {
    if (!data) return { nodes: [], edges: [], counts: null };
    const links = data.edges.filter((e) => LINK_CATEGORIES.includes(e.category));
    const linked = new Set(links.filter((e) => e.category === "verified").flatMap((e) => [e.from, e.to]));
    const kept = data.nodes
      .filter((n) => n.kind !== "decayflag" || flags)
      .map((n) => ({ ...n, orphan: n.kind === "requirement" && data.mode !== "requirements" && !linked.has(n.id) }));
    const ids = new Set(kept.map((n) => n.id));
    const shownEdges = data.edges.filter((e) => ids.has(e.from) && ids.has(e.to));
    const byCategory = Object.fromEntries(LINK_CATEGORIES.map((c) => [c, links.filter((e) => e.category === c).length]));
    return { nodes: kept, edges: shownEdges, counts: { ...byCategory, nodes: kept.length, edges: shownEdges.length } };
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

  return (
    <div className="kg-page mx-auto w-full max-w-[1500px] pb-8">
      <div className="kg-crumb">
        <span className="kg-crumb-mark">Shared layer</span>
        <span className="kg-crumb-sep">/</span>
        <span className="kg-crumb-current">Knowledge graph</span>
      </div>

      <header className="kg-hero">
        <div className="min-w-0">
          <h1>Unified Software Knowledge Graph</h1>
          <p>One shared graph that all four components write to: requirements, code structure and the traced connections between them. Select a node or an edge to inspect it.</p>
        </div>
        <div className="kg-project" title={project || undefined}>
          <Database size={15} className="shrink-0 text-indigo-500" />
          <span>{project || "No repository selected"}</span>
        </div>
      </header>

      {apiError && (
        <div className="kg-alert" role="alert">
          <AlertTriangle size={17} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">The API is not reachable ({apiError}).</p>
            <p className="mt-0.5">Start it from the project folder with <code className="rounded bg-amber-100 px-1">python -m apps.api.server</code> and make sure Neo4j is running.</p>
          </div>
        </div>
      )}

      <section className="kg-stats" aria-label="Graph summary">
        {counts ? (
          <>
            {STAT_CHIPS.map(([key, label, dot]) => (
              <span key={key} className="kg-stat" style={{ "--dot": dot }}><i /><b>{counts[key]}</b>{label}</span>
            ))}
            <span className="kg-stat"><b>{counts.nodes}</b>nodes</span>
            <span className="kg-stat"><b>{counts.edges}</b>relationships</span>
          </>
        ) : (
          <span className="kg-stat">{project ? (graph.loading ? "Loading graph…" : "No graph data") : "Choose a repository to see its graph"}</span>
        )}
      </section>

      <section className="kg-board" aria-label="Knowledge graph">
        <div className="kg-toolbar">
          <label className="kg-search">
            <Search size={15} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && focusFirstMatch()}
              placeholder="Search the graph, Enter to focus"
              aria-label="Search the graph"
            />
          </label>
          <div className="kg-seg" role="group" aria-label="What to show">
            {MODES.map(([value, label]) => (
              <button key={value} type="button" aria-pressed={mode === value} onClick={() => { setMode(value); setSelected(null); }}>{label}</button>
            ))}
          </div>
          <label className="kg-check">
            <input type="checkbox" checked={flags} onChange={(event) => setFlags(event.target.checked)} />
            Decay records
          </label>
          <button type="button" className="kg-btn" onClick={() => setArrange((value) => value + 1)}>Arrange</button>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px]">
          <UskgGraph className="kg-canvas h-[68vh] max-h-[720px] min-h-[480px]" nodes={nodes} edges={edges} selected={selected} onSelect={setSelected} search={search} arrangeToken={arrange} focusRef={focusRef} />
          <aside className="kg-inspector max-h-[720px] overflow-auto border-t border-slate-100 p-4 xl:border-l xl:border-t-0">
            <Inspector selected={selected} nodes={nodes} edges={edges} />
          </aside>
        </div>

        <footer className="kg-legend">
          <p className="kg-legend-title">Legend</p>
          {LEGEND.map(([label, color]) => (
            <span key={label}><i className="inline-block h-3 w-3 shrink-0 rounded-full" style={{ background: color }} />{label}</span>
          ))}
          <span><i className="inline-block h-3 w-3 shrink-0 rounded-full border border-dashed border-slate-400" />Unlinked requirement</span>
          <span><i className="inline-block h-0.5 w-6 shrink-0 bg-slate-400" />Verified link</span>
          <span><i className="inline-block w-6 shrink-0 border-t-2 border-dashed border-red-500" />Broken link</span>
        </footer>
      </section>
    </div>
  );
};

export default KnowledgeGraph;
