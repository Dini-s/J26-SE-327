import { linkLabel } from "../component/traceability/linkStatus";
import { useCallback, useMemo, useState } from "react";
import { postJson, useApi, useProject } from "../api/c4";
import StatusBadge from "../component/common/StatusBadge";
import { useActivity } from "../component/traceability/useActivity";
import { Card, Empty, TraceHeader } from "../component/traceability/common";

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

function changeBadge(r) {
  if (r.state === "running") return <StatusBadge type="info">checking</StatusBadge>;
  if (r.state === "stopped") return <StatusBadge type="warning">stopped</StatusBadge>;
  if (!r.rechecks.length) return <StatusBadge type="info">nothing to check</StatusBadge>;
  if (r.rechecks.some((c) => c.status === "pending_review")) return <StatusBadge type="warning">needs review</StatusBadge>;
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
        {c.broken ? <StatusBadge type="danger">broken</StatusBadge> : <StatusBadge type={c.status && c.status !== "verified" ? "warning" : "success"}>{c.restored ? "restored" : linkLabel(c.status || "verified")}</StatusBadge>}
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
  else if (run.rechecks.some((c) => c.status === "pending_review")) banner = <Notice tone="warn">Changed code needs human review before these links count as approved.</Notice>;
  else if (run.rechecks.some((c) => c.restored)) banner = <Notice tone="ok">{run.rechecks.filter((c) => c.restored).length} link(s) restored. Old decay flags are resolved and kept as history.</Notice>;
  else banner = <Notice tone="ok">No link broken. The AI still considers the code related ({run.rechecks.length} checked).</Notice>;
  return (
    <Card title={`Run results, ${clock(run.started)}`} action={changeBadge(run)}>
      <div className="space-y-3">
        {banner}
        <p className="text-xs text-slate-400">Historical result of this scan. View saved links for current link health.</p>
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
  const runsApi = useApi(enc ? `/api/change-runs?project=${enc}` : null, { pollMs: 3000 });
  const unlinked = useApi(enc ? `/api/unlinked?project=${enc}` : null, { pollMs: 5000 });
  const syncApi = useApi(enc ? `/api/repo-sync?project=${enc}` : null, { pollMs: 5000 });
  const reloadRuns = runsApi.reload;
  const reloadUnlinked = unlinked.reload;
  const refresh = useCallback(() => { reloadRuns(); reloadUnlinked(); }, [reloadRuns, reloadUnlinked]);
  const { busy } = useActivity(refresh);
  const [sel, setSel] = useState(null);
  const [force, setForce] = useState(false);
  const [scanHint, setScanHint] = useState("");
  const [github, setGithub] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const connectGitHub = async () => {
    setConnecting(true);
    setScanHint("");
    try {
      const config = await postJson("/api/github", { action: "status" });
      setGithub(config);
      await postJson("/api/github", { action: "connect", project });
      syncApi.reload();
      setScanHint("Webhook mode enabled. Complete webhook setup on GitHub to receive pushes.");
    } catch (error) { setScanHint(`Error: ${error.message}`); }
    finally { setConnecting(false); }
  };
  const runs = useMemo(() => runsApi.data?.runs ?? [], [runsApi.data]);
  const selected = runs.find((r) => r.id === sel) || runs[0] || null;
  const links = unlinked.data?.links ?? 0;
  const connection = syncApi.data;
  const waitingForWebhook = connection?.mode === "webhook" && !connection.lastDelivery && !connection.pending && connection.state === "watching";
  const syncState = waitingForWebhook ? "awaiting webhook" : connection?.pending && connection.state === "watching" ? "queued" : connection?.state;
  const scan = async () => {
    setScanHint("");
    try {
      await postJson("/api/scan", { project, force });
      setScanHint("Scanning the links for drift.");
      setSel(null);
      refresh();
    } catch (error) { setScanHint(`Error: ${error.message}`); }
  };
  return (
    <div className="mx-auto w-full max-w-[1500px]">
      <TraceHeader title="Code changes"
        subtitle="Track commits and review affected trace links."
        apiError={projectsError || runsApi.error || syncApi.error} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="min-w-0 space-y-5">
          <Card title="Connected repository">
            {syncApi.loading && !connection ? <p className="text-sm text-slate-500">Loading connection...</p> : connection?.connected ? (
              <div className="space-y-3 text-xs text-slate-500">
                <div className="flex items-start justify-between gap-3">
                  <a href={connection.url} target="_blank" rel="noreferrer" className="break-all text-[13px] font-medium text-slate-800 hover:text-indigo-600">{connection.url.replace("https://github.com/", "")}</a>
                  <StatusBadge type={connection.error ? "danger" : waitingForWebhook ? "warning" : connection.state === "checking" || connection.pending ? "info" : "success"}>{syncState}</StatusBadge>
                </div>
                <p><span className="font-mono text-slate-700">{connection.branch}</span><span className="mx-2 text-slate-300">·</span>{connection.mode === "webhook" ? "Push webhooks" : `Polling every ${connection.interval}s`}</p>
                <p>Last sync: {clock(connection.syncedAt) || "Not yet"}{connection.head && <span className="ml-2 font-mono text-slate-400">{connection.head.slice(0, 8)}</span>}</p>
                {connection.mode !== "webhook" && <button type="button" disabled={connecting || busy} onClick={connectGitHub} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-indigo-600 disabled:opacity-40">{connecting ? "Connecting..." : "Enable webhooks"}</button>}
                {github?.installUrl && <a href={github.installUrl} target="_blank" rel="noreferrer" className="block text-xs text-indigo-600">Manage GitHub access</a>}
                {waitingForWebhook && <p className="rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-800">No push received yet. For VS Code tunnels, port 8001 must be Public. Check GitHub's recent deliveries if a commit is missing.</p>}
                {connection.error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{connection.error}</p>}
                {connection.changes && <p>{connection.changes.modified.length} modified · {connection.changes.added.length} added · {connection.changes.deleted.length} deleted</p>}
                {connection.commits?.[0] && <p className="rounded-lg bg-slate-50 px-3 py-2 text-slate-600">{connection.commits[connection.commits.length - 1].message}</p>}
                <details className="border-t border-slate-100 pt-3">
                  <summary className="cursor-pointer text-[11px] text-slate-400">Connection details</summary>
                  <div className="mt-3 space-y-2 text-[11px] leading-5">
                    {connection.mode === "webhook" && <p>Last push: {connection.lastWebhookAt ? clock(connection.lastWebhookAt) : connection.lastDelivery ? "Received" : "Not received"}</p>}
                    <p>Last checked: {connection.checkedAt ? clock(connection.checkedAt) : "Not yet"}</p>
                    <p>{connection.mode === "webhook" ? "Keep the API and public tunnel running." : "Keep the API running."} Updates wait while another analysis is active.</p>
                    {connection.commits?.map((commit) => <p key={commit.sha}><span className="mr-2 font-mono text-slate-400">{commit.sha.slice(0, 8)}</span>{commit.message}</p>)}
                  </div>
                </details>
              </div>
            ) : <p className="text-[13px] text-slate-600">Connect a GitHub repository for automatic updates, or scan existing graph data below.</p>}
          </Card>
          <Card title="Drift scan">
            <p className="text-[13px] text-slate-600">{!project ? "Choose a project above." : !links ? "Create trace links first on the Link requirements page." : `${links} trace links available to check.`}</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-[12px] text-slate-600">
                <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} className="accent-indigo-600" />
                Include unchanged links
              </label>
              <button type="button" disabled={!links || busy} onClick={scan} className="ml-auto rounded-lg bg-indigo-600 px-4 py-2.5 text-[13px] font-semibold text-white disabled:opacity-40">Scan for drift</button>
            </div>
            {scanHint && <p className={`mt-2 text-[13px] ${scanHint.startsWith("Error") ? "text-red-600" : "text-slate-500"}`}>{scanHint}</p>}
          </Card>
        </div>
        <div className="min-w-0 space-y-5">
          <Card title="Drift checks" action={<span className="text-[12px] text-slate-500">{runs.length}</span>}>
            <div className="max-h-56 space-y-1 overflow-auto">
              {!runs.length && <p className="p-3 text-[13px] text-slate-400">Checks appear here after a source change or manual scan.</p>}
              {runs.map((run) => <button key={run.id} type="button" onClick={() => setSel(run.id)} className={`w-full rounded-lg border px-3 py-2 text-left ${selected?.id === run.id ? "border-indigo-300 bg-indigo-50" : "border-transparent hover:bg-slate-50"}`}>
                <div className="flex items-center justify-between gap-2"><span className="truncate font-mono text-[12px]">{run.files.join(", ") || "monitor pass"}</span>{changeBadge(run)}</div>
                <p className="mt-1 text-[12px] text-slate-500">{run.rechecks.length} links checked · {ago(run.started)}</p>
              </button>)}
            </div>
          </Card>
          {selected ? <ChangeResult run={selected} /> : <Card><Empty>No drift check yet. Push a source change to your connected branch after generating trace links.</Empty></Card>}
        </div>
      </div>
    </div>
  );
};

export default TraceabilityChanges;
