import { linkLabel, linkTone } from "../component/traceability/linkStatus";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Check } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { postJson, useApi, useProject, useRefresh } from "../api/c4";
import { Callout, Card, Chip, EmptyState, FileBadge, PageHeader } from "../component/traceability/ui";
import RequirementText from "../component/traceability/RequirementText";
import { codeLocation } from "../component/traceability/utils";

const keyOf = (item) => `${item.requirement}||${item.code}`;
const labels = { correct: "Matches", wrong: "Does not match", unsure: "Unsure" };
const reviewStatus = { correct: "verified", wrong: "rejected", unsure: "pending_review" };
const tones = { correct: "green", wrong: "red", unsure: "amber" };
const percent = (value) => value == null ? "—" : `${Math.round(value * 100)}%`;

function ReviewStatistics({ stats }) {
  if (!stats) return null;
  return <details className="rounded-xl border border-slate-200 bg-white p-5">
    <summary className="cursor-pointer text-xs font-medium text-slate-600">Review statistics <span className="ml-2 font-normal text-slate-400">{stats.labelled} of {stats.sample} reviewed</span></summary>
    <div className="mt-5 space-y-4 text-xs text-slate-500">
      <div><p>Human-reviewed precision</p><p className="mt-1 text-2xl font-semibold text-slate-800">{percent(stats.precision)}</p><p className="mt-2 text-[11px]">Matches ÷ (matches + does not match). Unsure is excluded.</p>{stats.ci95 && <p className="mt-1 text-[11px]">95% confidence interval: {percent(stats.ci95[0])}–{percent(stats.ci95[1])}</p>}</div>
      <p>{stats.correct} matches · {stats.wrong} do not match · {stats.unsure} unsure</p>
      <div className="border-t border-slate-100 pt-3"><p className="mb-2 font-medium text-slate-600">Human-reviewed precision by AI confidence</p>{stats.byConfidence.map((bucket) => <p key={bucket.label} className="flex justify-between py-1"><span>{bucket.label}</span><span>{percent(bucket.precision)} ({bucket.correct}/{bucket.correct + bucket.wrong})</span></p>)}</div>
      <p className="text-[11px] leading-5 text-slate-400">Small samples have wide uncertainty. These reviews measure accuracy; they do not change graph links.</p>
    </div>
  </details>;
}

function LinkInspector({ item, project, label, onSaved, index, count, onMove, onSaving, onReload }) {
  const code = useApi(`/api/code-text?code=${encodeURIComponent(item.code)}&full=1`);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lock = useRef(false);
  const mounted = useRef(false);
  const file = codeLocation(item.code);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const mark = useCallback(async (choice) => {
    if (!reviewing || lock.current || code.loading || code.error || !code.data) return;
    lock.current = true; setSaving(true); onSaving(true); setError(""); setNotice("");
    try {
      await postJson("/api/label", { project, requirement: item.requirement, code: item.code, label: choice, text_hash: item.textHash });
      if (!mounted.current) return;
      onSaved(keyOf(item), choice, item);
      setNotice(choice === "wrong" ? "Rejected. USKG updated; this link no longer counts as approved." : choice === "correct" ? "Approved. USKG and traceability graph updated." : "Left pending review. This link does not count as approved.");
      setReviewing(false);
    } catch (failure) {
      if (mounted.current) setError(`Could not save review: ${failure.message}. Try again.`);
    } finally {
      if (mounted.current) { lock.current = false; setSaving(false); onSaving(false); }
    }
  }, [item, project, onSaved, reviewing, onSaving, code.loading, code.error, code.data]);
  useEffect(() => {
    if (!reviewing) return undefined;
    const onKey = (event) => {
      if (event.target.closest?.('input, textarea, select, [contenteditable="true"]') || event.metaKey || event.ctrlKey || event.altKey || event.repeat || lock.current) return;
      const choice = { "1": "correct", "2": "wrong", "3": "unsure" }[event.key];
      if (choice) { event.preventDefault(); mark(choice); }
      else if (event.key === "ArrowRight" && index < count - 1) { event.preventDefault(); onMove(1); }
      else if (event.key === "ArrowLeft" && index > 0) { event.preventDefault(); onMove(-1); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [reviewing, mark, index, count, onMove]);
  return <Card title="Trace candidate" action={<Chip tone={label ? tones[label] : linkTone(item.status)}>{linkLabel(label ? reviewStatus[label] : item.status)}</Chip>}>
    <p className="text-[11px] font-medium text-slate-400">Requirement · {item.requirement}</p>
    <div className="mt-2 text-sm leading-7 text-slate-800"><RequirementText text={item.requirementText} /></div>
    <div className="mt-5 border-t border-slate-100 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="flex min-w-0 items-center gap-2 break-all text-xs font-semibold text-slate-700"><FileBadge name={file.name} />{file.name}</p><span className="text-[11px] text-slate-400">AI confidence {item.confidence == null ? "—" : Number(item.confidence).toFixed(2)}</span></div>
      <p className="mt-2 break-all text-[10px] leading-5 text-slate-400">{file.project ? `${file.project} / ` : ""}{file.path}</p>
      {code.error ? <div role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">Unable to load source: {code.error} <button type="button" onClick={code.reload} className="ml-2 underline">Retry</button></div> : code.loading && !code.data ? <p role="status" className="py-8 text-xs text-slate-400">Loading full source…</p> : <pre aria-label="Full source code" className="mt-3 max-h-[480px] overflow-auto whitespace-pre rounded-lg border border-slate-100 bg-slate-50 p-4 font-mono text-[11px] leading-6 text-slate-600"><code>{code.data?.text || "No source code stored for this file."}</code></pre>}
    </div>
    <details className="mt-4 text-xs text-slate-500"><summary className="cursor-pointer">AI reasoning</summary><p className="mt-2 leading-6">{item.reason || "No AI reasoning recorded."}</p></details>
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
      {!reviewing ? <button type="button" disabled={code.loading || !!code.error || !code.data} onClick={() => { setReviewing(true); setNotice(""); }} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:border-indigo-200 hover:text-indigo-600">{label ? "Edit review" : "Review this link"}</button> : <div className="flex flex-wrap items-center gap-2" aria-label="Human review choices">{["correct", "wrong", "unsure"].map((choice, position) => <button key={choice} type="button" disabled={saving || code.loading || !!code.error || !code.data} onClick={() => mark(choice)} aria-pressed={label === choice} className={`rounded-lg border px-3 py-2 text-xs disabled:opacity-40 ${label === choice ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-600 hover:border-indigo-200"}`}>{labels[choice]} <span className="ml-1 text-[10px] text-slate-400">{position + 1}</span></button>)}<button type="button" disabled={saving} onClick={() => { setReviewing(false); setError(""); }} className="px-2 py-2 text-xs text-slate-400 disabled:opacity-40">Cancel</button></div>}
      <div className="flex items-center gap-2"><span className="mr-1 text-[10px] text-slate-400">{index + 1} / {count}</span><button type="button" disabled={saving || index === 0} onClick={() => onMove(-1)} aria-label="Previous link" className="rounded-md border border-slate-200 p-1.5 text-slate-500 disabled:opacity-30"><ChevronLeft size={14} /></button><button type="button" disabled={saving || index >= count - 1} onClick={() => onMove(1)} aria-label="Next link" className="rounded-md border border-slate-200 p-1.5 text-slate-500 disabled:opacity-30"><ChevronRight size={14} /></button></div>
    </div>
    {reviewing && !saving && <p className="mt-3 text-[10px] text-slate-400">Optional review · 1 Matches · 2 Does not match · 3 Unsure</p>}
    {saving && <p role="status" className="mt-3 text-xs text-slate-500">Saving review…</p>}
    {notice && <p role="status" className="mt-3 flex items-center gap-1 text-xs text-emerald-700"><Check size={13} />{notice}</p>}
    {error && <p role="alert" className="mt-3 text-xs text-red-600">{error} <button type="button" onClick={onReload} className="ml-2 underline">Reload candidate</button></p>}
  </Card>;
}
function ReviewWorkspace({ project, projectsError, totalLinks }) {
  const { bump } = useRefresh();
  const [params] = useSearchParams();
  const wantedRequirement = params.get("requirement");
  const wantedCode = params.get("code");
  const enc = project ? encodeURIComponent(project) : null;
  const direct = wantedRequirement && wantedCode ? `&requirement=${encodeURIComponent(wantedRequirement)}&code=${encodeURIComponent(wantedCode)}` : "";
  const [state, setState] = useState(wantedRequirement && wantedCode ? "all" : "needs_review");
  const [page, setPage] = useState(1);
  const queueApi = useApi(enc ? `/api/review-queue?project=${enc}&state=${state}&page=${page}&page_size=40${direct}` : null);
  const legacyApi = useApi(enc ? `/api/labeling?project=${enc}&n=40${direct}` : null);
  const api = {
    ...queueApi,
    data: queueApi.data || (queueApi.error ? legacyApi.data : null),
    error: queueApi.data ? queueApi.error : legacyApi.error,
    reload: queueApi.data ? queueApi.reload : legacyApi.reload,
  };
  const [held, setHeld] = useState(null);
  const items = useMemo(() => {
    const rows = api.data?.items ?? [];
    return held && !rows.some((row) => keyOf(row) === keyOf(held)) ? [...rows.slice(0, 39), held] : rows;
  }, [api.data, held]);
  const [picked, setPicked] = useState(() => wantedRequirement && wantedCode ? `${wantedRequirement}||${wantedCode}` : null);
  const [saving, setSaving] = useState(false);
  const [overrides, setOverrides] = useState({});
  const [inspectorVersion, setInspectorVersion] = useState(0);
  const index = Math.max(0, items.findIndex((item) => keyOf(item) === picked));
  const current = items[index];
  const { reload } = api;
  const saved = useCallback((key, choice, item) => { setHeld({ ...item, label: choice, status: reviewStatus[choice] }); setPicked(key); setOverrides((previous) => ({ ...previous, [key]: { label: choice, hash: item.textHash } })); reload(); bump(); }, [reload, bump]);
  const labelOf = (item) => { const override = overrides[keyOf(item)]; return override && override.hash === item.textHash ? override.label : item.label || ({ verified: "correct", rejected: "wrong", deferred: "unsure" }[item.status]); };
  const choose = (key) => { setHeld(null); setPicked(key); setInspectorVersion((version) => version + 1); };
  const move = (delta) => {
    const next = items[Math.max(0, Math.min(items.length - 1, index + delta))];
    if (next) choose(keyOf(next));
  };
  return <div>
    <PageHeader page="Evaluate" title="Link review" description="Review the saved queue. AI confidence is evidence, not an approval decision." apiError={projectsError || api.error} />
    {!queueApi.data && queueApi.error && <Callout tone="warn">The status filter needs the API to be restarted. Showing the fixed sample until then.</Callout>}
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <label className="text-xs font-medium text-slate-600">Show <select value={state} onChange={(event) => { setState(event.target.value); setPage(1); setHeld(null); }} className="ml-2 rounded-lg border border-slate-200 bg-white px-2 py-2"><option value="needs_review">Needs review</option><option value="deferred">Deferred</option><option value="verified">Approved</option><option value="rejected">Rejected</option><option value="all">All</option></select></label>
      {api.data?.pageSize && <div className="flex items-center gap-2 text-xs text-slate-500"><span>Page {page} of {Math.max(1, Math.ceil(api.data.total / api.data.pageSize))}</span><button type="button" disabled={page === 1 || saving} onClick={() => setPage((value) => value - 1)} className="rounded border px-2 py-1 disabled:opacity-40">Previous</button><button type="button" disabled={page >= Math.ceil(api.data.total / api.data.pageSize) || saving} onClick={() => setPage((value) => value + 1)} className="rounded border px-2 py-1 disabled:opacity-40">Next</button></div>}
    </div>
    {!project ? <Card><EmptyState title="Select a project first" /></Card> : api.error && !api.data ? <Card><button type="button" onClick={reload} className="text-xs text-indigo-600">Retry loading saved links</button></Card> : !api.data ? <Card><EmptyState title="Loading saved links…" /></Card> : !items.length ? <Card><EmptyState title="No candidates to review"><Link to="/traceability/link" className="text-indigo-600">Create trace links first.</Link></EmptyState></Card> : <>
      <div className="grid items-start gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="min-w-0"><Card title={(api.data.total ?? totalLinks) > items.length ? `Review sample · ${items.length}` : `Trace candidates · ${items.length}`}>
          <div className="max-h-[600px] space-y-2 overflow-auto">{items.map((item) => {
            const label = labelOf(item);
            return <button type="button" disabled={saving} key={keyOf(item)} onClick={() => choose(keyOf(item))} aria-pressed={keyOf(item) === keyOf(current)} className={`w-full rounded-lg border p-3 text-left ${keyOf(item) === keyOf(current) ? "border-indigo-200 bg-indigo-50/40" : "border-transparent hover:bg-slate-50"}`}>
              <p className="text-xs font-medium text-slate-700">{item.requirement}</p><p className="mt-1.5 break-all text-[11px] text-slate-500">{codeLocation(item.code).name}</p><p className="mt-2 text-[10px] text-slate-400">{linkLabel(label ? reviewStatus[label] : item.status)}</p>
            </button>;
          })}</div>
        </Card></aside>
        <main className="min-w-0"><LinkInspector key={`${keyOf(current)}:${inspectorVersion}`} item={current} project={project} label={labelOf(current)} onSaved={saved} index={index} count={items.length} onMove={move} onSaving={setSaving} onReload={() => { setHeld(null); setOverrides({}); reload(); setInspectorVersion((version) => version + 1); }} /></main>
      </div>
      <div className="mt-5"><ReviewStatistics stats={api.data.stats} /></div>
    </>}
  </div>;
}
export default function TraceabilityLabeling() {
  const { project, projects, error } = useProject();
  const totalLinks = projects.find((item) => item.project === project)?.links || 0;
  return <ReviewWorkspace key={project || "none"} project={project} projectsError={error} totalLinks={totalLinks} />;
}
