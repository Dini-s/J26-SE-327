import { Link } from "react-router-dom";
import { useState } from "react";
import { Check, ChevronUp, Database, Plus, Settings } from "lucide-react";
import { useApi, useProject } from "../api/c4";
import AddProjectDialog from "./AddProjectDialog";

/** Repository picker at the bottom of the sidebar. The choice drives every C4 page. */
const RepoSwitcher = () => {
  const { projects, project, setProject } = useProject();
  const health = useApi("/api/health", { pollMs: 15000 }).data;
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const current = projects.find((p) => p.project === project);

  const dot = (ok, label) => (
    <span key={label} title={label} className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`} />
  );

  return (
    <div className="relative shrink-0 border-t border-white/10 p-3">
      {open && (
        <div className="absolute inset-x-3 bottom-full mb-1 max-h-64 overflow-auto rounded-xl border border-white/10 bg-[#0f1b33] p-1 shadow-xl">
          {projects.map((p) => (
            <button
              key={p.project}
              type="button"
              onClick={() => {
                setProject(p.project);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition hover:bg-white/10 ${p.project === project ? "text-white" : "text-slate-300"}`}
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{p.project}</span>
                <span className="block text-[10px] text-slate-500">{p.requirements} req · {p.code_entities} files · {p.links} links</span>
              </span>
              {p.project === project && <Check size={14} className="shrink-0 text-blue-400" />}
            </button>
          ))}
          <Link to="/settings" onClick={() => setOpen(false)} className="mt-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs text-slate-300 hover:bg-white/10">
            <Settings size={14} /> Manage projects
          </Link>
          {projects.length === 0 && <p className="px-3 py-3 text-xs text-slate-400">No repositories found. Is the C4 API running?</p>}
          <button
            type="button"
            onClick={() => { setOpen(false); setAdding(true); }}
            className="mt-1 flex w-full items-center gap-2 rounded-lg border border-dashed border-white/15 px-2.5 py-2 text-left text-xs text-blue-300 transition hover:bg-white/10"
          >
            <Plus size={14} /> Add a project
          </button>
        </div>
      )}
      <AddProjectDialog open={adding} onClose={() => setAdding(false)} onAdded={(key) => { setProject(key); setOpen(false); }} />

      <div className="rounded-xl border border-blue-400/20 bg-blue-500/5 p-3">
        <p className="mb-2 text-[9px] font-medium uppercase tracking-wide text-slate-500">Active Repository</p>
        <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-2 text-left" aria-label="Change repository">
          <span className="flex min-w-0 items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-500/10">
              <Database size={14} className="text-blue-400" />
            </span>
            <span className="truncate text-xs font-medium text-slate-200">{project ?? "No repository"}</span>
          </span>
          <ChevronUp size={14} className={`shrink-0 text-slate-400 transition-transform ${open ? "" : "rotate-180"}`} />
        </button>

        <div className="my-3 h-px bg-white/10" />
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-300">
            {current ? `${current.requirements} req · ${current.code_entities} files · ${current.links} links` : "-"}
          </span>
          {health && (
            <span className="flex gap-1.5">
              {dot(health.neo4j.connected, "Knowledge graph")}
              {dot(health.llm.reachable, "AI model")}
              {dot(health.redis.reachable, "Redis")}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default RepoSwitcher;
