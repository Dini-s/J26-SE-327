import { useCallback, useMemo, useState } from "react";
import { postJson, useApi, useProject } from "../api/c4";
import StatusBadge from "../component/common/StatusBadge";
import { ActivityBanner } from "../component/traceability/Activity";
import { useActivity } from "../component/traceability/useActivity";
import { Card, Empty, TraceHeader } from "../component/traceability/common";
import { shortName } from "../component/traceability/utils";

const EXAMPLES = {
  iTrust: ["For Login Failures, the IP Address of the machine, transaction type = 1, and timestamp are recorded."],
  "CM-1": [
    "The DPU-CCM shall check the length of a received DPU_CMD against an expected value from a lookup table indexed by FUNCTION code. If the received value does not match the expected, then the command will be discarded, and an error will be reported.",
  ],
  jbehave: ["MetaFilter is always using the PrintStreamEmbedderMonitor, even when the Embedder is using a different monitor. The Embedder should pass its own monitor to each MetaFilter it creates."],
  eTour: ["Use case SearchSite: The user searches for a specific site on the computer. The system looks up sites matching the search criteria entered by the user and shows the results."],
  "spring-petclinic": ["The system shall let a clinic employee delete a pet and all of its visits after a confirmation."],
};

const ago = (iso) => {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
};
const clock = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "");
const dur = (a, b) => {
  const s = Math.max(0, Math.round(((b ? new Date(b) : new Date()) - new Date(a)) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
};
const dirOf = (id) => String(id).replace(/\\/g, "/").split("/").slice(0, -1).join("/");

function runBadge(r) {
  if (r.state === "running") return <StatusBadge type="info">checking {r.done}/{r.total}</StatusBadge>;
  if (r.state === "stopped") return <StatusBadge type="warning">stopped</StatusBadge>;
  return r.linked ? <StatusBadge type="success">{r.linked} linked</StatusBadge> : <StatusBadge type="info">no link</StatusBadge>;
}

const Notice = ({ tone, children }) => {
  const style = { info: "border-blue-200 bg-blue-50 text-blue-900", ok: "border-emerald-200 bg-emerald-50 text-emerald-900", warn: "border-amber-200 bg-amber-50 text-amber-900", bad: "border-red-200 bg-red-50 text-red-900" }[tone];
  return <div className={`rounded-lg border px-4 py-3 text-sm ${style}`}>{children}</div>;
};

function RunResult({ run, texts, open, onToggle }) {
  const finished = run.state === "finished";
  let banner;
  if (run.state === "running") banner = <Notice tone="info">The AI is checking file {Math.min(run.done + 1, run.total)} of {run.total}. {dur(run.started)} so far.</Notice>;
  else if (run.state === "stopped") banner = <Notice tone="warn">This run stopped early: {run.done} of {run.total} files were checked.</Notice>;
  else if (run.linked) banner = <Notice tone="ok">Linked to {run.linked} code file{run.linked > 1 ? "s" : ""} in {dur(run.started, run.finished)}. Saved to the graph.</Notice>;
  else banner = <Notice tone="warn">The AI confirmed none of the {run.total} candidates ({dur(run.started, run.finished)}). No link was saved.</Notice>;

  const steps = [
    ["Shortlist code", run.candidates.length ? `${run.total} candidates` : "searching...", run.candidates.length ? "done" : "active"],
    ["AI checks each file", `${run.done} of ${run.total}`, finished || run.state === "stopped" ? "done" : run.state === "running" && run.candidates.length ? "active" : ""],
    ["Save links", finished ? `${run.linked} saved` : "as each is confirmed", finished ? "done" : ""],
  ];

  return (
    <Card title={`Result, ${clock(run.started)}`} action={runBadge(run)}>
      <div className="space-y-3">
        {banner}
        <ol className="grid gap-2 sm:grid-cols-3">
          {steps.map(([title, detail, state], i) => (
            <li key={title} className={`rounded-lg border px-3 py-2 ${state === "done" ? "border-emerald-200" : state === "active" ? "border-blue-300" : "border-slate-200"}`}>
              <p className="text-[11px] text-slate-500">Step {i + 1}{state === "done" ? " (done)" : state === "active" ? " (running)" : ""}</p>
              <p className="text-[13px] font-medium text-slate-800">{title}</p>
              <p className="text-[12px] text-slate-500">{detail}</p>
            </li>
          ))}
        </ol>
      </div>

      {run.requirements.slice(0, 20).map((req) => {
        const cands = run.candidates.filter((c) => c.requirement === req);
        return (
          <div key={req} className="mt-4 border-t border-slate-100 pt-3">
            <p className="text-[13px] font-semibold text-indigo-600">{req}</p>
            <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{texts[req] || ""}</p>
            <table className="mt-3 w-full text-[13px]">
              <tbody>
                {cands.map((c) => {
                  const key = `${run.id}|${req}|${c.target}`;
                  const decision = c.decision === "linked" ? <StatusBadge type="success">linked</StatusBadge> : c.decision === "waiting" ? <StatusBadge type="info">checking</StatusBadge> : <StatusBadge type="warning">not linked</StatusBadge>;
                  return (
                    <FragmentCand key={key} c={c} decision={decision} expanded={open.has(key)} onToggle={() => onToggle(key)} />
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}
    </Card>
  );
}

function FragmentCand({ c, decision, expanded, onToggle }) {
  return (
    <>
      <tr onClick={onToggle} className="cursor-pointer border-b border-slate-50 hover:bg-slate-50">
        <td className="w-full py-2">
          <p className="font-mono text-[12px] text-slate-800">{c.file || shortName(c.target)}</p>
          <p className="text-[11px] text-slate-400">{dirOf(c.target)}</p>
        </td>
        <td className="whitespace-nowrap px-2 text-right tabular-nums text-slate-600">{c.confidence == null ? "" : `conf ${c.confidence.toFixed(2)}`}</td>
        <td className="whitespace-nowrap px-2 text-right text-[11px] text-slate-400">{c.seconds ? `${Math.round(c.seconds)} s` : ""}</td>
        <td className="text-right">{decision}</td>
      </tr>
      {expanded && c.reason && (
        <tr>
          <td colSpan={4} className="pb-3 text-[12px] leading-relaxed text-slate-600">{c.reason}</td>
        </tr>
      )}
    </>
  );
}

const TraceabilityLink = () => {
  const { project, error: projectsError } = useProject();
  const enc = project ? encodeURIComponent(project) : null;
  const unlinked = useApi(enc ? `/api/unlinked?project=${enc}` : null);
  const runsApi = useApi(enc ? `/api/link-runs?project=${enc}` : null, { pollMs: 3000 });
  const reloadUnlinked = unlinked.reload;
  const reloadRuns = runsApi.reload;

  const refresh = useCallback(() => {
    reloadUnlinked();
    reloadRuns();
  }, [reloadUnlinked, reloadRuns]);
  const { activity, busy } = useActivity(refresh);

  const [exTopK, setExTopK] = useState(3);
  const [topK, setTopK] = useState(3);
  const [text, setText] = useState("");
  const [reqId, setReqId] = useState("");
  const [exHint, setExHint] = useState("");
  const [hint, setHint] = useState("");
  const [sel, setSel] = useState(null);
  const [open, setOpen] = useState(() => new Set());

  const runs = useMemo(() => runsApi.data?.runs ?? [], [runsApi.data]);
  const texts = runsApi.data?.texts ?? {};
  const u = unlinked.data;

  // a just-submitted requirement is "pending" until its run shows up in the history
  const pendingId = sel && sel.startsWith("pending:") ? sel.slice(8) : null;
  const pendingRun = pendingId ? runs.find((r) => r.requirements.includes(pendingId)) : null;
  const pending = pendingId && !pendingRun ? pendingId : null;
  const activeSel = pendingRun ? pendingRun.id : sel;
  const selected = pending ? null : runs.find((r) => r.id === activeSel) || runs[0] || null;

  let exText;
  let canLink = false;
  if (!project) exText = "Choose a project above.";
  else if (!u) exText = "Reading this project from the knowledge graph...";
  else if (!u.requirements) exText = "This project has no requirements yet. They appear here once C1 has written them, or type one below.";
  else if (!u.codeFiles) exText = `${u.requirements} requirements, but no code files yet. They appear here once C2 has written them.`;
  else if (!u.unlinked) exText = `All ${u.requirements} requirements already have a trace link. New requirements and new commits are handled below and in Code changes.`;
  else {
    canLink = true;
    exText = `${u.unlinked} of ${u.requirements} requirements have no trace link yet. For each one, the ${exTopK} most likely of ${u.codeFiles} code files are checked by the AI; confirmed links are saved. About ${Math.max(1, Math.round((u.unlinked * exTopK * 52) / 60))} min.`;
  }

  const linkExisting = async () => {
    setExHint("");
    try {
      const r = await postJson("/api/link-existing", { project, top_k: exTopK });
      setSel(null);
      setExHint(`Creating trace links for ${r.requirements} requirements. About ${r.minutes} min.`);
      refresh();
    } catch (error) {
      setExHint(`Error: ${error.message}`);
    }
  };

  const submit = async () => {
    setHint("");
    if (!project) return setHint("Error: choose a project first.");
    if (text.trim().length < 15) return setHint("Error: write the requirement as a full sentence.");
    try {
      const r = await postJson("/api/link", { text: text.trim(), id: reqId.trim(), top_k: topK, project });
      setText("");
      setReqId("");
      setSel(`pending:${r.id}`);
      setHint(`${r.id} added. Checking about ${r.minutes || topK} min.`);
      refresh();
    } catch (error) {
      setHint(`Error: ${error.message}`);
    }
  };

  const examples = EXAMPLES[project] || [];
  const toggle = (key) =>
    setOpen((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <div className="mx-auto w-full max-w-[1500px]">
      <TraceHeader
        title="Link requirements to code"
        subtitle="Find the code that implements a requirement; the AI checks each candidate, and confirmed links are saved to the knowledge graph."
        apiError={projectsError || runsApi.error}
      />
      <ActivityBanner activity={activity} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="min-w-0 space-y-5">
          <Card title="Requirements already in the graph" subtitle="Written by C1">
            <p className="text-[13px] text-slate-600">{exText}</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-[12px] text-slate-600">
                Code files per requirement
                <select value={exTopK} onChange={(event) => setExTopK(Number(event.target.value))} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[13px] outline-none">
                  {[3, 5, 10].map((k) => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                disabled={!canLink || busy}
                onClick={linkExisting}
                className="ml-auto rounded-lg bg-indigo-600 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {canLink ? `Create trace links for ${u.unlinked} requirement${u.unlinked === 1 ? "" : "s"}` : "Create trace links"}
              </button>
            </div>
            {exHint && <p className={`mt-2 text-[13px] ${exHint.startsWith("Error") ? "text-red-600" : "text-slate-500"}`}>{exHint}</p>}
          </Card>

          <Card title="New requirement" subtitle="Saved to the selected project">
            <label className="text-[12px] font-medium text-slate-600" htmlFor="req-text">Requirement text</label>
            <textarea
              id="req-text"
              rows={3}
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  submit();
                }
              }}
              placeholder="For login failures, the IP address of the machine and a timestamp are recorded."
              className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-indigo-400"
            />
            <div className="mt-3 flex flex-wrap items-end gap-4">
              <div>
                <label className="text-[12px] font-medium text-slate-600" htmlFor="req-id">Id (optional)</label>
                <input id="req-id" value={reqId} maxLength={40} onChange={(event) => setReqId(event.target.value)} placeholder="NEW-020" className="mt-1.5 block w-36 rounded-lg border border-slate-200 px-3 py-1.5 text-[13px] outline-none focus:border-indigo-400" />
              </div>
              <div>
                <span className="text-[12px] font-medium text-slate-600">Code files to check</span>
                <div className="mt-1.5 inline-flex rounded-lg border border-slate-200 p-0.5">
                  {[3, 5, 10].map((k) => (
                    <button key={k} type="button" onClick={() => setTopK(k)} className={`rounded-md px-3 py-1 text-[13px] font-medium ${topK === k ? "bg-slate-900 text-white" : "text-slate-600"}`}>{k}</button>
                  ))}
                </div>
                <span className="ml-2 text-[12px] text-slate-500">about {topK} min</span>
              </div>
              <button type="button" disabled={busy} onClick={submit} className="ml-auto rounded-lg bg-indigo-600 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40">
                Find trace links
              </button>
            </div>
            {hint && <p className={`mt-2 text-[13px] ${hint.startsWith("Error") ? "text-red-600" : "text-slate-500"}`}>{hint}</p>}
            {examples.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px]">
                <span className="text-slate-500">Examples:</span>
                {examples.map((e) => (
                  <button key={e} type="button" onClick={() => setText(e)} className="max-w-xs truncate rounded border border-dashed border-slate-300 px-2 py-0.5 text-slate-600 hover:border-indigo-400 hover:text-indigo-600">
                    {e.slice(0, 48)}...
                  </button>
                ))}
              </div>
            )}
          </Card>

        </div>

        <div className="min-w-0 space-y-5">
        <Card title="Run history" action={<span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{runs.length}</span>} className="self-start">
          <div className="-m-2 max-h-[190px] space-y-1 overflow-auto">
            {runs.length === 0 ? (
              <p className="px-3 py-6 text-center text-[13px] text-slate-400">Linked requirements appear here.</p>
            ) : (
              runs.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => {
                    setSel(r.id);
                    setOpen(new Set());
                  }}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition ${selected && r.id === selected.id ? "border-indigo-300 bg-indigo-50/60" : "border-transparent hover:bg-slate-50"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[12px] font-medium text-slate-800">
                      {r.requirements.slice(0, 2).join(", ")}
                      {r.requirements.length > 2 ? ` +${r.requirements.length - 2}` : ""}
                    </span>
                    {runBadge(r)}
                  </div>
                  <p className="mt-1 line-clamp-2 text-[12px] text-slate-500">{texts[r.requirements[0]] || ""}</p>
                  <p className="mt-1 text-[11px] text-slate-400" title={clock(r.started)}>{ago(r.started)}</p>
                </button>
              ))
            )}
          </div>
        </Card>
          <div className="max-h-[calc(100vh-420px)] min-h-[260px] space-y-5 overflow-auto rounded-2xl">
          {pending && (
            <Notice tone="info">Starting. Shortlisting code for {pending}...</Notice>
          )}
          {selected ? (
            <RunResult run={selected} texts={texts} open={open} onToggle={toggle} />
          ) : (
            !pending && <Card><Empty>No run selected. Create trace links above; the result appears here.</Empty></Card>
          )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TraceabilityLink;
