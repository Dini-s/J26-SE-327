import { useEffect, useId, useRef, useState } from "react";
import { FolderOpen, GitBranch, X, RefreshCw, LoaderCircle, Check, ChevronRight } from "lucide-react";
import { postJson, useRefresh } from "../api/c4";

/** Popup to add a project: a public GitHub repository, or a folder inside the home folder on this computer. */
const AddProjectDialog = ({ open, onClose, onAdded }) => {
  const { bump } = useRefresh();
  const formId = useId();
  const dialogRef = useRef(null);
  const [connecting, setConnecting] = useState(false);
  const [mode, setMode] = useState("github");
  const [url, setUrl] = useState("");
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [branch, setBranch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const [folders, setFolders] = useState(null);
  const [browsing, setBrowsing] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [github, setGithub] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [useApp, setUseApp] = useState(false);
  const loadGitHub = async () => {
    setConnecting(true);
    setError("");
    try {
      const config = await postJson("/api/github", { action: "status" });
      setGithub(config);
      if (!config.configured) throw new Error("GitHub App is not configured on the server.");
      const result = await postJson("/api/github", { action: "repositories" });
      setRepositories(result.repositories);
      setUseApp(true);
      setUrl("");
      setBranch("");
    } catch (err) { setError(err.message); }
    finally { setConnecting(false); }
  };

  const browse = async (folder) => {
    setBrowsing(true);
    setError("");
    try {
      const result = await postJson("/api/folders", folder ? { path: folder } : {});
      setFolders(result);
      setChoosing(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBrowsing(false);
    }
  };

  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape" && !busy && !browsing && !connecting) onClose();
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled])');
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialogRef.current)) {
        event.preventDefault(); first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [open, busy, browsing, connecting, onClose]);

  const repositoryName = url.trim().match(/^https:\/\/github\.com\/[^/]+\/([^/?#]+)\/?$/i)?.[1]?.replace(/\.git$/i, "") || "";
  const folderName = path.replace(/\\/g, "/").split("/").filter(Boolean).pop() || "";
  const suggestedName = (mode === "github" ? (repositoryName ? `Aspire/${repositoryName}` : "") : folderName).slice(0, 60);
  const projectName = nameEdited ? name : suggestedName;

  if (!open) return null;

  const reset = () => {
    setUrl(""); setPath(""); setName(""); setNameEdited(false); setBranch(""); setError(""); setDone(null); setFolders(null); setChoosing(false); setUseApp(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = mode === "github"
        ? { kind: "github", url: url.trim(), name: projectName.trim() || suggestedName, branch: branch.trim(), useApp }
        : { kind: "folder", path: path.trim(), name: projectName.trim() || suggestedName };
      const result = await postJson("/api/import", body);
      setDone(result);
      bump();
      onAdded?.(result.key);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    if (busy || browsing || connecting) return;
    reset();
    onClose();
  };

  const locked = busy || browsing || connecting;
  const input = "mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-[13px] text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50 disabled:opacity-60";
  const label = "block text-xs font-medium text-slate-600";

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/35 p-4" onClick={close}>
      <section ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={`${formId}-title`} className="flex max-h-[90dvh] w-full max-w-[440px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl outline-none" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-center justify-between px-6 pb-5 pt-6"><h2 id={`${formId}-title`} className="text-lg font-semibold tracking-tight text-slate-900">{done ? "Project added" : "Add project"}</h2><button type="button" onClick={close} disabled={locked} aria-label="Close" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40"><X size={18} /></button></header>
        {done ? <>
          <div className="px-6 pb-6"><p className="flex items-center gap-2 break-all text-sm text-slate-800"><Check size={16} className="shrink-0 text-emerald-600" />{done.name}</p><p className="mt-2 text-xs text-slate-400">{done.files} source files added.</p></div>
          <footer className="flex justify-end border-t border-slate-100 px-6 py-4"><button type="button" onClick={() => { reset(); onClose(); }} className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-700">Done</button></footer>
        </> : <>
          <form id={formId} onSubmit={submit} className="space-y-4 overflow-y-auto px-6 pb-6" aria-busy={busy}>
            <div className="flex gap-1 rounded-lg bg-slate-100 p-1" role="group" aria-label="Project source">
              {[["github", "GitHub", GitBranch], ["folder", "Local folder", FolderOpen]].map(([value, title, Icon]) => <button key={value} type="button" disabled={locked} aria-pressed={mode === value} onClick={() => { setMode(value); setError(""); }} className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition ${mode === value ? "bg-white text-slate-800 shadow-sm" : "text-slate-400 hover:text-slate-700"}`}><Icon size={14} />{title}</button>)}
            </div>
            {mode === "github" ? <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button type="button" disabled={locked} onClick={loadGitHub} className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50">{connecting ? <LoaderCircle size={13} className="animate-spin" /> : useApp ? <RefreshCw size={13} /> : <GitBranch size={13} />}{connecting ? "Connecting..." : useApp ? "Refresh repositories" : "Choose from GitHub"}</button>
                {github?.installUrl && <a href={github.installUrl} target="_blank" rel="noreferrer" className="text-[11px] text-slate-400 hover:text-indigo-600">Manage access</a>}
              </div>
              {useApp ? <>
                <label className={label}>Repository<select disabled={locked} value={url} required onChange={(event) => { setUrl(event.target.value); setBranch(repositories.find((repo) => repo.url === event.target.value)?.defaultBranch || ""); }} className={input}><option value="">Select repository</option>{repositories.map((repo) => <option key={repo.url} value={repo.url}>{repo.name}{repo.private ? " (private)" : ""}</option>)}</select></label>
                {!repositories.length && <p className="text-xs text-slate-500">Grant repository access on GitHub, then refresh.</p>}
                <button type="button" disabled={locked} onClick={() => { setUseApp(false); setUrl(""); }} className="text-[11px] text-slate-400 hover:text-indigo-600">Use a public URL instead</button>
              </> : <label className={label}>Repository URL<input disabled={locked} className={input} value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repo" required /></label>}
            </> : <div>
              <button type="button" disabled={locked} onClick={() => browse(path || undefined)} className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-xs font-medium text-slate-600 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50">{browsing ? <LoaderCircle size={16} className="animate-spin" /> : <FolderOpen size={16} />}{browsing ? "Opening..." : path ? "Change folder" : "Choose folder"}</button>
              {path && <p className="mt-2 break-all text-[11px] text-slate-400">{path}</p>}
              {choosing && folders && <div className="mt-3 overflow-hidden rounded-lg border border-slate-200" aria-label="Choose project folder" aria-busy={browsing}>
                <div className="border-b border-slate-100 bg-slate-50 p-3"><p className="break-all text-[10px] text-slate-500">{folders.path}</p><div className="mt-2 flex gap-4"><button type="button" disabled={browsing || !folders.parent} onClick={() => browse(folders.parent)} className="text-[11px] text-indigo-600 disabled:opacity-30">Up</button><button type="button" disabled={browsing} onClick={() => browse()} className="text-[11px] text-indigo-600">Home</button></div></div>
                <div className="max-h-36 overflow-y-auto p-1">{folders.folders.map((folder) => <button key={folder.path + folder.name} type="button" disabled={browsing} onClick={() => browse(folder.path)} className="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-xs text-slate-600 hover:bg-slate-50"><FolderOpen size={13} className="shrink-0 text-slate-400" /><span className="min-w-0 flex-1 break-all">{folder.name}</span><ChevronRight size={12} className="text-slate-300" /></button>)}{!folders.folders.length && <p className="p-3 text-xs text-slate-400">No subfolders.</p>}</div>
                <div className="flex justify-end gap-3 border-t border-slate-100 p-3"><button type="button" disabled={browsing} onClick={() => setChoosing(false)} className="text-[11px] text-slate-400">Cancel</button><button type="button" disabled={browsing} onClick={() => { setPath(folders.path); setChoosing(false); }} className="rounded-md bg-indigo-600 px-3 py-1.5 text-[11px] font-medium text-white">Select folder</button></div>
              </div>}
            </div>}
            <label className={label}>Project name<input disabled={locked} className={input} value={projectName} onChange={(event) => { setName(event.target.value); setNameEdited(true); }} placeholder="Auto-filled from your selection" maxLength={60} /></label>
            {nameEdited && suggestedName && projectName !== suggestedName && <button type="button" disabled={locked} onClick={() => { setName(""); setNameEdited(false); }} className="text-[11px] text-indigo-600">Reset name</button>}
            {mode === "github" && <details className="text-xs text-slate-500"><summary className="cursor-pointer text-[11px]">Branch {branch ? `· ${branch}` : "(optional)"}</summary><input aria-label="Branch" disabled={locked} className={input} value={branch} onChange={(event) => setBranch(event.target.value)} placeholder="Default branch" /></details>}
            {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-xs leading-5 text-red-700">{error}</p>}
          </form>
          <footer className="flex shrink-0 justify-end gap-2 border-t border-slate-100 px-6 py-4"><button type="button" disabled={locked} onClick={close} className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">Cancel</button><button form={formId} type="submit" disabled={locked || (mode === "folder" ? !path || choosing : !url.trim())} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-40">{busy && <LoaderCircle size={13} className="animate-spin" />}{busy ? "Adding..." : "Add project"}</button></footer>
        </>}
      </section>
    </div>
  );
};

export default AddProjectDialog;
