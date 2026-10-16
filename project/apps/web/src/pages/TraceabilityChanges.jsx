import { useCallback, useMemo, useState } from "react";
import { postJson, useApi, useProject } from "../api/c4";
import StatusBadge from "../component/common/StatusBadge";
import { ActivityBanner } from "../component/traceability/Activity";
import { useActivity } from "../component/traceability/useActivity";
import { Card, Empty, TraceHeader } from "../component/traceability/common";
import { shortName } from "../component/traceability/utils";

const MUTATIONS = {
  unrelated_replacement: { title: "Replace with unrelated text", desc: "The file now does something else entirely.", expect: "should break", tone: "danger" },
  negate_behavior: { title: "Reverse the meaning", desc: "\"shall\" becomes \"shall not\".", expect: "should break", tone: "danger" },
  change_numbers: { title: "Change the numbers", desc: "Limits and sizes are changed.", expect: "may break", tone: "warning" },
  strip_to_first_sentence: { title: "Keep only the first sentence", desc: "The rest of the file is deleted.", expect: "should break", tone: "danger" },
  cosmetic_control: { title: "Harmless comment", desc: "A formatting note only. Control case.", expect: "should hold", tone: "success" },
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

function changeBadge(r) {
  if (r.state === "running") return <StatusBadge type="info">checking</StatusBadge>;
  if (r.state === "stopped") return <StatusBadge type="warning">stopped</StatusBadge>;
  if (!r.rechecks.length) return <StatusBadge type="info">nothing to check</StatusBadge>;
  return r.broken ? <StatusBadge type="danger">{r.broken} broken</StatusBadge> : <StatusBadge type="success">all hold</StatusBadge>;
}

const Notice = ({ tone, children }) => {
  const style = { info: "border-blue-200 bg-blue-50 text-blue-900", ok: "border-emerald-200 bg-emerald-50 text-emerald-900", warn: "border-amber-200 bg-amber-50 text-amber-900", bad: "border-red-200 bg-red-50 text-red-900" }[tone];
  return <div className={`rounded-lg border px-4 py-3 text-sm ${style}`}>{children}</div>;
};

function Recheck({ c, message }) {
  const [shown, setShown] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(message.event));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[12px] text-slate-800">{c.requirement} to {c.file}</span>
        {c.broken ? <StatusBadge type="danger">broken</StatusBadge> : <StatusBadge type="success">still holds</StatusBadge>}
      </div>
      <div className="mt-2 flex items-center gap-3 text-[12px] text-slate-500">
        <span className="tabular-nums">{c.before.toFixed(2)}</span>
        <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
          <span className="absolute inset-y-0 left-0 rounded-full bg-slate-300" style={{ width: `${c.before * 100}%` }} />
          <span className={`absolute inset-y-0 left-0 rounded-full ${c.broken ? "bg-red-500" : "bg-emerald-500"}`} style={{ width: `${c.after * 100}%` }} />
        </span>
        <span className="font-medium tabular-nums text-slate-700">{c.after.toFixed(2)}</span>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-slate-600">{c.reason}</p>
      {message && (
        <div className="mt-3 border-t border-slate-100 pt-3 text-[12px]">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-slate-600">Message to C3</span>
            {message.delivered ? <StatusBadge type="success">delivered over Redis</StatusBadge> : <StatusBadge type="warning">recorded, Redis not running</StatusBadge>}
            <button type="button" onClick={() => setShown(!shown)} className="text-indigo-600 hover:underline">{shown ? "Hide" : "Show"}</button>
            <button type="button" onClick={copy} className="text-indigo-600 hover:underline">{copied ? "Copied" : "Copy"}</button>
          </div>
          {shown && <pre className="mt-2 overflow-auto rounded bg-slate-50 p-2 font-mono text-[12px]">{JSON.stringify(message.event, null, 2)}</pre>}
        </div>
      )}
    </div>
  );
}

function ChangeResult({ run }) {
  let banner;
  if (run.state === "running") banner = <Notice tone="info">Re-checking the links of {run.files.join(", ")}. {dur(run.started)} so far.</Notice>;
  else if (run.state === "stopped") banner = <Notice tone="warn">This check stopped before the end.</Notice>;
  else if (!run.rechecks.length) banner = <Notice tone="warn">{run.trigger === "monitor" ? "Nothing needed a re-check: no requirement or code text changed since the links were verified. No drift found." : "Nothing was re-checked: the file has no link, or its text did not change."}</Notice>;
  else if (run.broken) banner = <Notice tone="bad">{run.broken} of {run.rechecks.length} link(s) broken by this change. They are marked decayed, and C3 was notified.</Notice>;
  else banner = <Notice tone="ok">No link broken. The AI still considers the code related ({run.rechecks.length} checked).</Notice>;
  return (
    <Card title={`Result, ${clock(run.started)}`} action={changeBadge(run)}>
      <div className="space-y-3">
        {banner}
        {run.rechecks.map((c) => (
          <Recheck key={`${c.requirement}|${c.target}`} c={c} message={run.messages.find((m) => m.event.requirementId === c.requirement && m.event.codeEntityId === c.target)} />
        ))}
      </div>
    </Card>
  );
}

const TraceabilityChanges = () => {
  const { project, error: projectsError } = useProject();
  const enc = project ? encodeURIComponent(project) : null;
  const filesApi = useApi(enc ? `/api/files?project=${enc}` : null);
  const runsApi = useApi(enc ? `/api/change-runs?project=${enc}` : null, { pollMs: 3000 });
  const unlinked = useApi(enc ? `/api/unlinked?project=${enc}` : null);
  const reloadFiles = filesApi.reload;
  const reloadRuns = runsApi.reload;
  const reloadUnlinked = unlinked.reload;

  const refresh = useCallback(() => {
    reloadFiles();
    reloadRuns();
    reloadUnlinked();
  }, [reloadFiles, reloadRuns, reloadUnlinked]);
  const { activity, busy } = useActivity(refresh);

  const [filter, setFilter] = useState("");
  const [file, setFile] = useState(null);
  const [mutation, setMutation] = useState("unrelated_replacement");
  const [lastEdit, setLastEdit] = useState(null);
  const [sel, setSel] = useState(null);
  const [force, setForce] = useState(false);
  const [scanHint, setScanHint] = useState("");
  const [commitHint, setCommitHint] = useState("");

  const files = useMemo(() => (Array.isArray(filesApi.data) ? filesApi.data : []), [filesApi.data]);
  const runs = useMemo(() => runsApi.data?.runs ?? [], [runsApi.data]);
  const links = unlinked.data?.links ?? 0;

  // the chosen file, or the first one while nothing (valid) is chosen
  const activeFile = file && files.some((f) => f.id === file) ? file : files[0]?.id ?? null;
  // a just-made commit is "pending" until its run shows up in the history
  const pendingRun = sel === "pending" && runs[0] && lastEdit && runs[0].files.includes(shortName(lastEdit.code_id)) ? runs[0] : null;
  const pendingNow = sel === "pending" && !pendingRun;
  const activeSel = pendingRun ? pendingRun.id : sel;
  const selected = pendingNow ? null : runs.find((r) => r.id === activeSel) || runs[0] || null;
  const q = filter.trim().toLowerCase();
  const list = files.filter((f) => !q || f.id.toLowerCase().includes(q) || f.requirements.join(" ").toLowerCase().includes(q));

  const scan = async () => {
    setScanHint("");
    try {
      await postJson("/api/scan", { project, force });
      setScanHint("Scanning the links for drift.");
      setSel(null);
      refresh();
    } catch (error) {
      setScanHint(`Error: ${error.message}`);
    }
  };
  const commit = async () => {
    setCommitHint("");
    if (!activeFile) return setCommitHint("Error: pick a code file first.");
    try {
      const r = await postJson("/api/commit", { code_id: activeFile, mutation, project });
      setLastEdit(r);
      setSel("pending");
      setCommitHint(`Commit made. Re-checking the links of ${shortName(activeFile)}.`);
      refresh();
    } catch (error) {
      setCommitHint(`Error: ${error.message}`);
    }
  };
  const undo = async () => {
    try {
      const r = await postJson("/api/undo", { project });
      setCommitHint(`Undone: ${r.restored_texts} file(s) restored, ${r.flags_removed} decay record(s) removed.`);
      setLastEdit(null);
      refresh();
    } catch (error) {
      setCommitHint(`Error: ${error.message}`);
    }
  };
  const reset = async () => {
    if (!project || !window.confirm(`Delete all links and decay records of ${project}, and the requirements typed here? Loaded requirements and code stay.`)) return;
    try {
      const r = await postJson("/api/reset", { project });
      setCommitHint(`Reset: ${r.deleted_links} links and ${r.deleted_flags} decay records removed.`);
      refresh();
    } catch (error) {
      setCommitHint(`Error: ${error.message}`);
    }
  };

  const buttonPrimary = "rounded-lg bg-indigo-600 px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40";
  const hintClass = (t) => `mt-2 text-[13px] ${t.startsWith("Error") ? "text-red-600" : "text-slate-500"}`;

  return (
    <div className="mx-auto w-full max-w-[1500px]">
      <TraceHeader
        title="Code changes"
        subtitle="Re-check trace links after a code change and inspect any broken connections. A link that no longer holds is marked decayed and C3 is told over Redis."
        apiError={projectsError || runsApi.error}
      />
      <ActivityBanner activity={activity} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="min-w-0 space-y-5">
          <Card title="Drift detection" subtitle="Scan the trace links of this project">
            <p className="text-[13px] text-slate-600">
              {!project ? "Choose a project above." : !links ? "This project has no trace links yet, so there is nothing to scan. Create trace links first (Link requirements page)." : `${links} trace link${links === 1 ? "" : "s"}. A scan re-checks the links whose requirement or code text changed since they were verified. A link that no longer holds is marked decayed, and C3 is told over Redis.`}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-[12px] text-slate-600">
                <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} className="accent-indigo-600" />
                Re-check every link, even unchanged ones (slower)
              </label>
              <button type="button" disabled={!links || busy} onClick={scan} className={`${buttonPrimary} ml-auto`}>Scan for drift</button>
            </div>
            {scanHint && <p className={hintClass(scanHint)}>{scanHint}</p>}
          </Card>

          <Card title="Simulate a commit" subtitle="Edits the stored text of a linked code file (demo only, on your local graph), then re-checks its links. 'Undo my changes' restores it.">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[12px] font-medium text-slate-600">1. Select a linked code file</span>
              <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter" className="w-44 rounded-lg border border-slate-200 px-2.5 py-1 text-[13px] outline-none focus:border-indigo-400" />
            </div>
            <div className="mt-2 max-h-56 divide-y divide-slate-100 overflow-auto rounded-lg border border-slate-200">
              {files.length === 0 ? (
                <p className="p-4 text-center text-[13px] text-slate-400">No linked code yet. Link a requirement first.</p>
              ) : list.length === 0 ? (
                <p className="p-4 text-[13px] text-slate-400">No file matches.</p>
              ) : (
                list.map((f) => (
                  <button key={f.id} type="button" onClick={() => setFile(f.id)} className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-slate-50 ${f.id === activeFile ? "bg-indigo-50" : ""}`}>
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-[12px] text-slate-800">{shortName(f.id)}</span>
                      <span className="block truncate text-[11px] text-slate-400">{dirOf(f.id)}</span>
                    </span>
                    <span className="flex shrink-0 flex-wrap justify-end gap-1">
                      {f.requirements.slice(0, 2).map((r) => (
                        <span key={r} className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] text-indigo-600">{r}</span>
                      ))}
                      {f.status === "decayed" && <StatusBadge type="danger">broken</StatusBadge>}
                      {f.modified && <StatusBadge type="warning">edited</StatusBadge>}
                    </span>
                  </button>
                ))
              )}
            </div>

            <p className="mt-5 text-[12px] font-medium text-slate-600">2. What the commit changes</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {Object.entries(MUTATIONS).map(([key, m]) => (
                <button key={key} type="button" aria-pressed={mutation === key} onClick={() => setMutation(key)} className={`rounded-lg border p-3 text-left transition ${mutation === key ? "border-indigo-500 ring-2 ring-indigo-500/20" : "border-slate-200 hover:border-slate-300"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-medium text-slate-800">{m.title}</span>
                    <StatusBadge type={m.tone}>{m.expect}</StatusBadge>
                  </div>
                  <p className="mt-1 text-[12px] text-slate-500">{m.desc}</p>
                </button>
              ))}
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
              <button type="button" disabled={busy} onClick={commit} className={buttonPrimary}>Commit the change</button>
              <button type="button" onClick={undo} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-[13px] font-medium text-slate-700 transition hover:border-indigo-200 hover:text-indigo-600">Undo my changes</button>
              <button type="button" disabled={busy} onClick={reset} className="ml-auto rounded-lg border border-red-200 bg-white px-4 py-2 text-[13px] font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-40">Reset this project</button>
            </div>
            {commitHint && <p className={hintClass(commitHint)}>{commitHint}</p>}
          </Card>

        </div>

        <div className="min-w-0 space-y-5">
        <Card title="Commits checked" action={<span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{runs.length}</span>} className="self-start">
          <div className="-m-2 max-h-[170px] space-y-1 overflow-auto">
            {runs.length === 0 ? (
              <p className="px-3 py-6 text-center text-[13px] text-slate-400">Commits you make appear here.</p>
            ) : (
              runs.map((r) => (
                <button key={r.id} type="button" onClick={() => setSel(r.id)} className={`w-full rounded-lg border px-3 py-2 text-left transition ${selected && r.id === selected.id ? "border-indigo-300 bg-indigo-50/60" : "border-transparent hover:bg-slate-50"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[12px] font-medium text-slate-800">{r.files.join(", ") || "monitor pass"}</span>
                    {changeBadge(r)}
                  </div>
                  <p className="mt-1 text-[12px] text-slate-500">{r.rechecks.length} link(s) re-checked{r.messages.length ? `, ${r.messages.length} message(s) to C3` : ""}</p>
                  <p className="mt-1 text-[11px] text-slate-400" title={clock(r.started)}>{ago(r.started)}</p>
                </button>
              ))
            )}
          </div>
        </Card>
          <div className="max-h-[calc(100vh-400px)] min-h-[260px] space-y-5 overflow-auto rounded-2xl">
          {lastEdit && (
            <Card title={`Change to ${shortName(lastEdit.code_id)}`} action={<StatusBadge type="info">{(MUTATIONS[lastEdit.mutation] || {}).title || lastEdit.mutation}</StatusBadge>}>
              <div className="grid gap-4 md:grid-cols-2">
                {[["Before", lastEdit.before], ["After", lastEdit.after]].map(([label, body]) => (
                  <div key={label}>
                    <p className="mb-2 text-[12px] font-medium text-slate-500">{label}</p>
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 font-mono text-[12px] leading-relaxed text-slate-700">{body}</pre>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {pendingNow && <Notice tone="info">Commit received. Starting the re-check...</Notice>}
          {selected ? <ChangeResult run={selected} /> : !pendingNow && <Card><Empty>No change checked yet. Select a file and a change to inspect the affected trace links.</Empty></Card>}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TraceabilityChanges;
