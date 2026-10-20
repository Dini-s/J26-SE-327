import { useState } from "react";
import { Plus, Trash2, X, Check } from "lucide-react";
import { postJson, useProject, useRefresh } from "../api/c4";
import AddProjectDialog from "../Layouts/AddProjectDialog";

export default function Settings() {
  const { projects, project, setProject, error: projectsError, loading } = useProject();
  const [adding, setAdding] = useState(false);
  const { bump } = useRefresh();
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const removeProject = async () => {
    const target = deleting;
    setBusy(true);
    setError("");
    try {
      const result = await postJson("/api/projects/delete", { project: target.project, confirmation: target.project });
      if (project === target.project) setProject(projects.find((p) => p.project !== target.project)?.project || null);
      setDeleting(null);
      setNotice(result.warnings?.length ? result.warnings.join(" ") : `Deleted ${target.project}.`);
      bump();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="mx-auto w-full max-w-[880px] py-2">
      <h1 className="mb-7 text-2xl font-semibold tracking-tight text-slate-900">Settings</h1>
      {projectsError && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-xs text-red-700">{projectsError}</p>}
      {notice && <div role="status" className="mb-4 flex items-center justify-between gap-3 rounded-lg bg-emerald-50 px-4 py-3 text-xs text-emerald-800"><span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="Dismiss message"><X size={14} /></button></div>}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-800">Projects <span className="ml-1 text-xs font-normal text-slate-400">{projects.length}</span></h2>
          <button type="button" onClick={() => setAdding(true)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-700"><Plus size={14} />Add project</button>
        </header>
        <div className="divide-y divide-slate-100">
          {loading && !projects.length ? <p className="p-8 text-center text-xs text-slate-400">Loading projects...</p> : !projects.length ? <p className="p-10 text-center text-sm text-slate-400">No projects yet.</p> : projects.map((item) => (
            <div key={item.project} className="flex flex-wrap items-center gap-3 px-5 py-4">
              <div className="min-w-0 flex-1"><p className="break-all text-[13px] font-medium text-slate-800">{item.project}</p><p className="mt-1 text-[11px] text-slate-400">{item.requirements} requirements · {item.code_entities} files · {item.links} links</p></div>
              <div className="flex shrink-0 items-center gap-3">
                {project === item.project ? <span className="inline-flex items-center gap-1 text-[11px] text-indigo-600"><Check size={13} />Active</span> : <button type="button" onClick={() => setProject(item.project)} className="rounded-md px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-50 hover:text-indigo-600">Select</button>}
                <button type="button" onClick={() => { setDeleting(item); setError(""); }} aria-label={`Delete ${item.project}`} title="Delete project" className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={15} /></button>
              </div>
            </div>
          ))}
        </div>
      </section>
      {deleting && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/35 p-4" role="dialog" aria-modal="true" aria-labelledby="delete-project-title">
        <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
          <div className="flex items-center justify-between"><h2 id="delete-project-title" className="text-base font-semibold text-slate-900">Delete project?</h2><button type="button" disabled={busy} onClick={() => setDeleting(null)} aria-label="Close" className="text-slate-400 hover:text-slate-700"><X size={17} /></button></div>
          <p className="mt-4 break-all text-sm font-medium text-slate-800">{deleting.project}</p>
          <p className="mt-2 text-xs leading-6 text-slate-500">This permanently removes its graph data, links, history, and downloaded copy. Your original repository is kept.</p>
          {error && <p role="alert" className="mt-3 text-xs text-red-600">{error}</p>}
          <div className="mt-6 flex justify-end gap-2"><button type="button" disabled={busy} onClick={() => setDeleting(null)} className="rounded-lg border border-slate-200 px-4 py-2 text-xs text-slate-600">Cancel</button><button type="button" disabled={busy} onClick={removeProject} className="rounded-lg bg-red-600 px-4 py-2 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50">{busy ? "Deleting..." : "Delete project"}</button></div>
        </div>
      </div>}
      <AddProjectDialog open={adding} onClose={() => setAdding(false)} onAdded={(key) => setProject(key)} />
    </div>
  );
}
