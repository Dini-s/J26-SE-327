import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Loader2 } from "lucide-react";
import { postJson, useApi, useProject } from "../api/c4";
import StatusBadge from "../component/common/StatusBadge";
import { useActivity } from "../component/traceability/useActivity";
import { announceActivity } from "../component/traceability/activityBus";
import RequirementPicker from "../component/traceability/RequirementPicker";
import { Card, Empty, TraceHeader } from "../component/traceability/common";
import RequirementText from "../component/traceability/RequirementText";
import { codeLocation } from "../component/traceability/utils";

const clock = (iso) => iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
const duration = (start, end) => {
  const seconds = Math.max(0, Math.round(((end ? new Date(end) : new Date()) - new Date(start)) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
};
function RunBadge({ run }) {
  const running = run.state === "running";
  return <StatusBadge type={running ? "info" : run.state === "stopped" ? "warning" : run.linked ? "success" : "info"}>{running ? `Checking ${run.done}/${run.total}` : run.state === "stopped" ? "Stopped" : `${run.linked} saved`}</StatusBadge>;
}
function Candidate({ candidate, running }) {
  const file = codeLocation(candidate.target);
  const saved = candidate.decision === "linked";
  const waiting = candidate.decision === "waiting";
  const review = candidate.decision === "review";
  const decision = review ? "Needs review" : saved ? "Approved" : waiting ? running ? "Checking" : "Not checked" : "Not selected";
  return <details className="group border-b border-slate-100 last:border-0">
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-3 py-3 text-xs [&::-webkit-details-marker]:hidden">
      <span className="min-w-[120px] flex-1 break-all font-medium text-slate-700">{file.name}</span>
      <span className="whitespace-nowrap tabular-nums text-slate-400">AI {candidate.confidence == null ? "—" : Number(candidate.confidence).toFixed(2)}</span>
      <StatusBadge type={saved ? "success" : waiting ? "info" : "warning"}>{decision}</StatusBadge>
      <ChevronDown size={13} className="text-slate-400 group-open:rotate-180" />
    </summary>
    <div className="space-y-2 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
      {file.project && <p className="break-all">Repository: {file.project}</p>}
      <p className="break-all font-mono">{file.path}</p>
      <p>{candidate.reason || (waiting ? "No AI verdict was recorded." : "No reasoning recorded.")}</p>
      {candidate.seconds != null && <p className="text-[11px] text-slate-400">Checked in {Math.round(candidate.seconds)}s</p>}
    </div>
  </details>;
}
export function RunResult({ run, texts }) {
  const running = run.state === "running";
  return <Card title="Run results" subtitle={clock(run.started)}>
    <p className="text-sm font-medium text-slate-700">{run.linked} approved · {run.pending || 0} need review · {run.done} {run.done === 1 ? "file" : "files"} checked · {run.state === "stopped" && !run.finished ? "Stopped" : duration(run.started, run.finished)}</p>
    {running && <p role="status" className="mt-2 text-xs text-indigo-600">{run.total ? `Checking ${run.done} of ${run.total} candidates…` : "Preparing candidates…"}</p>}
    {run.state === "stopped" && <p className="mt-2 text-xs text-amber-700">Stopped early. {Math.max(0, run.total - run.done)} candidates were not checked.</p>}
    <p className="mt-2 text-[11px] text-slate-400">Results at run time. Later code changes may affect saved links.</p>
    <details className="mt-3 text-xs text-slate-500"><summary className="cursor-pointer">Pipeline details</summary><ol className="mt-2 space-y-1 pl-4"><li>1. Shortlist code: {run.candidates.length} candidates</li><li>2. AI verification: {run.done} of {run.total} checked</li><li>3. Save connections: {run.linked} links</li></ol></details>
    {run.requirements.slice(0, 20).map((id) => <section key={id} className="mt-5 border-t border-slate-100 pt-4">
      <h3 className="text-xs font-semibold text-slate-800">{id}</h3>
      <div className="mt-2 text-xs leading-6 text-slate-500"><RequirementText text={texts[id] || ""} /></div>
      <div className="mt-3 flex justify-between border-b border-slate-100 pb-2 text-[10px] text-slate-400"><span>Candidate file</span><span>AI confidence / decision</span></div>
      {run.candidates.filter((candidate) => candidate.requirement === id).map((candidate) => <Candidate key={candidate.target} candidate={candidate} running={running} />)}
    </section>)}
    {!!(run.linked || run.pending) && <div className="mt-4 flex flex-wrap gap-4 text-xs"><Link className="text-indigo-600 hover:underline" to="/traceability">View saved links</Link><Link className="text-slate-500 hover:text-indigo-600" to="/traceability/labeling">Review candidates</Link></div>}
  </Card>;
}

function LinkingWorkspace({ project, projectsError }) {
  const enc = project ? encodeURIComponent(project) : null;
  const unlinked = useApi(enc ? `/api/unlinked?project=${enc}` : null);
  const runsApi = useApi(enc ? `/api/link-runs?project=${enc}` : null, { pollMs: 3000 });
  const { reload: reloadUnlinked } = unlinked;
  const { reload: reloadRuns } = runsApi;
  const refresh = useCallback(() => { reloadUnlinked(); reloadRuns(); }, [reloadUnlinked, reloadRuns]);
  const { busy, reload: reloadActivity } = useActivity(refresh);
  const [mode, setMode] = useState("existing");
  const [topK, setTopK] = useState(3);
  const [chosen, setChosen] = useState([]);
  const [text, setText] = useState("");
  const [requirementId, setRequirementId] = useState("");
  const [selection, setSelection] = useState(null);
  const [hint, setHint] = useState("");
  const [starting, setStarting] = useState(false);
  const [launchedAt, setLaunchedAt] = useState(null);
  const mounted = useRef(false);
  const submitting = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const runs = useMemo(() => runsApi.data?.runs ?? [], [runsApi.data]);
  const texts = runsApi.data?.texts ?? {};
  const data = unlinked.data;
  const pendingId = selection?.startsWith("pending:") ? selection.slice(8) : null;
  const selected = pendingId ? runs.find((run) => run.requirements.includes(pendingId)) : runs.find((run) => run.id === selection) || runs[0];
  const pending = pendingId && !selected;
  const complete = data?.requirements > 0 && data.unlinked === 0;
  const canLink = !!project && data?.unlinked > 0 && data.codeFiles > 0;
  const launching = launchedAt != null && !runs.some((run) => Date.parse(run.started) >= launchedAt - 3000);
  useEffect(() => {
    if (launchedAt == null) return undefined;
    const timer = setTimeout(() => setLaunchedAt(null), 30000);
    return () => clearTimeout(timer);
  }, [launchedAt]);
  const locked = busy || starting || launching;
  const start = async (event) => {
    event.preventDefault();
    if (submitting.current || busy || !project) return;
    if (mode === "new" && text.trim().length < 15) { setHint("Error: write a requirement of at least 15 characters."); return; }
    if (mode === "existing" && !canLink) return;
    submitting.current = true; setStarting(true); setHint("");
    const existing = mode === "existing";
    announceActivity({ kind: "link", project });
    setLaunchedAt(Date.now());
    try {
      const result = await postJson(existing ? "/api/link-existing" : "/api/link", existing ? { project, top_k: topK, ...(chosen.length ? { requirement_ids: chosen } : {}) } : { project, text: text.trim(), id: requirementId.trim(), top_k: topK });
      if (!mounted.current) return;
      setChosen([]);
      setSelection(existing ? null : `pending:${result.id}`);
      if (!existing) { setText(""); setRequirementId(""); }
      setHint(existing ? `Started linking ${result.requirements} requirements.` : `${result.id} added. Finding trace links.`);
      refresh(); reloadActivity();
      [1200, 3000].forEach((delay) => setTimeout(() => { if (mounted.current) refresh(); }, delay));
    } catch (error) { announceActivity(null); if (mounted.current) { setLaunchedAt(null); setHint(`Error: ${error.message}`); } }
    finally { if (mounted.current) { submitting.current = false; setStarting(false); } }
  };
  return <div>
    <TraceHeader title="Link requirements" subtitle="Find and save AI-verified connections to code." apiError={projectsError || unlinked.error || runsApi.error} />
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="min-w-0 space-y-5">
        <Card>
          <div className="mb-5 flex gap-5 border-b border-slate-100" role="tablist" aria-label="Requirement source">
            {[["existing", "Existing requirements"], ["new", "New requirement"]].map(([value, label]) => <button key={value} role="tab" aria-selected={mode === value} type="button" disabled={starting} onClick={() => { setMode(value); setHint(""); }} className={`border-b-2 pb-3 text-xs font-medium ${mode === value ? "border-indigo-600 text-indigo-600" : "border-transparent text-slate-400"}`}>{label}</button>)}
          </div>
          <form onSubmit={start}>
            {mode === "existing" ? <>
              <p className="text-xs leading-6 text-slate-500">{!project ? "Select a project first." : unlinked.error ? "Unable to load requirements." : !data ? "Loading requirements…" : !data.requirements ? "No requirements yet. Add one or import them into the graph." : complete && data.pendingReview ? `${data.pendingReview} candidates need human review.` : complete && data.awaitingApproval ? `${data.awaitingApproval} requirements have no approved link. Review their candidates.` : complete ? `${data.requirements} ${data.requirements === 1 ? "requirement" : "requirements"} already linked.` : !data.codeFiles ? "Add code files before creating links." : `${data.unlinked} of ${data.requirements} requirements need links.`}</p>
              {canLink && data.ids?.length > 0 && <RequirementPicker ids={data.ids} texts={data.texts} chosen={chosen} onChange={setChosen} disabled={locked} />}
              {(data?.pendingReview > 0 || (complete && data?.awaitingApproval > 0)) && <Link className="mt-3 mr-4 inline-block text-xs font-medium text-indigo-600" to="/traceability/labeling">Review candidates →</Link>}
              {complete && <Link className="mt-3 inline-block text-xs font-medium text-indigo-600" to="/traceability">View saved links →</Link>}
            </> : <>
              <label className="block text-xs font-medium text-slate-600" htmlFor="req-text">Requirement</label>
              <textarea id="req-text" rows={4} value={text} onChange={(event) => setText(event.target.value)} disabled={starting} placeholder="Describe the behavior the system should provide…" required minLength={15} maxLength={2000} className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
              <label className="mt-4 block text-xs text-slate-500" htmlFor="req-id">ID (optional)</label><input id="req-id" value={requirementId} disabled={starting} onChange={(event) => setRequirementId(event.target.value)} maxLength={40} placeholder="Assigned automatically" className="mt-2 w-44 rounded-lg border border-slate-200 px-3 py-2 text-xs" />
            </>}
            {(mode === "new" || canLink) && <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
              <label className="text-xs text-slate-500">Candidates per requirement<select value={topK} disabled={locked} onChange={(event) => setTopK(Number(event.target.value))} className="ml-2 rounded-md border border-slate-200 px-2 py-1.5">{[3, 5, 10].map((count) => <option key={count}>{count}</option>)}</select></label>
              <button type="submit" disabled={locked || !project || (mode === "new" && text.trim().length < 15)} className="rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-medium text-white disabled:opacity-40">{starting || launching ? "Starting…" : mode === "new" ? "Find trace links" : chosen.length ? `Link ${chosen.length} selected` : "Create trace links"}</button>
            </div>}
            {hint && <p role="status" className={`mt-3 text-xs ${hint.startsWith("Error:") ? "text-red-600" : "text-slate-500"}`}>{hint}</p>}
          </form>
        </Card>
        {launching ? <Card><div role="status" className="flex items-start gap-3"><Loader2 size={18} className="mt-0.5 shrink-0 animate-spin text-indigo-500" /><div><p className="text-sm font-semibold text-slate-800">Starting the AI check…</p><p className="mt-1 text-xs leading-5 text-slate-500">Your request was sent. Results appear here by themselves, and progress also shows at the bottom right on every page, so you can open another page meanwhile.</p></div></div></Card> : pending ? <Card><p role="status" className="text-xs text-slate-500">Preparing candidates for {pendingId}…</p></Card> : selected ? <RunResult run={selected} texts={texts} /> : <Card><Empty>No run results yet.</Empty></Card>}
      </div>
      <aside className="min-w-0"><Card title="Run history" action={<span className="text-xs text-slate-400">{runs.length}</span>}>
        {!runs.length && <p className="py-4 text-xs text-slate-400">Your runs will appear here.</p>}
        <div className="max-h-[520px] space-y-2 overflow-auto">{runs.map((run) => <button type="button" key={run.id} onClick={() => setSelection(run.id)} aria-pressed={selected?.id === run.id} className={`w-full rounded-lg border p-3 text-left ${selected?.id === run.id ? "border-indigo-200 bg-indigo-50/50" : "border-transparent hover:bg-slate-50"}`}>
          <p className="truncate text-xs font-medium text-slate-700">{run.requirements.slice(0, 2).join(", ") || "Batch run"}</p>
          <div className="mt-2 line-clamp-2 text-[11px] leading-5 text-slate-400"><RequirementText text={texts[run.requirements[0]] || ""} /></div>
          <div className="mt-3"><RunBadge run={run} /></div><p className="mt-2 text-[10px] text-slate-400">{clock(run.started)}</p>
        </button>)}</div>
      </Card></aside>
    </div>
  </div>;
}
export default function TraceabilityLink() {
  const { project, error } = useProject();
  return <LinkingWorkspace key={project || "none"} project={project} projectsError={error} />;
}
