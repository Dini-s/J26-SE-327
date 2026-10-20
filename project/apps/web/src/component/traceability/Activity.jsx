import { Loader2, ChevronUp } from "lucide-react";
import { useApi, useProject } from "../../api/c4";
import { useLocation } from "react-router-dom";

const duration = (iso) => {
  if (!iso) return "";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
};

/** Compact progress dock, shown only on the matching workflow page and project. */
export function ActivityIndicator({ activity }) {
  const { pathname } = useLocation();
  const { project } = useProject();
  if (!activity || activity.state === "idle") return null;
  if (activity.project && activity.project !== project) return null;
  const workflow = activity.kind === "change" ? "/traceability/changes" : "/traceability/link";
  if (pathname.replace(/\/$/, "") !== workflow) return null;
  const linking = activity.kind === "link";
  const label = linking ? "Linking requirements" : activity.kind === "change" ? "Checking drift" : "Analysis running";
  const progress = linking && activity.total ? Math.min(100, Math.round(100 * (activity.done || 0) / activity.total)) : null;
  const count = linking && activity.total ? `${activity.done || 0}/${activity.total}` : activity.kind === "change" ? `${activity.checked || 0} checked` : null;
  return (
    <details className="group fixed bottom-5 right-5 z-40 max-w-[calc(100vw-2.5rem)]">
      <summary className="flex cursor-pointer list-none items-center gap-2.5 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-xs text-slate-600 shadow-[0_4px_20px_rgba(15,23,42,0.09)] outline-none transition hover:border-indigo-200 focus-visible:ring-2 focus-visible:ring-indigo-300 [&::-webkit-details-marker]:hidden" aria-label={`${label}${count ? `, ${count}` : ""}. Toggle progress details`}>
        <Loader2 size={14} className="shrink-0 animate-spin text-indigo-500" />
        <span className="font-medium">{label}</span>
        {count && <span className="border-l border-slate-200 pl-2.5 text-[11px] tabular-nums text-slate-400">{count}</span>}
        <ChevronUp size={12} className="text-slate-400 transition-transform group-open:rotate-180" />
      </summary>
      <div className="absolute bottom-full right-0 mb-3 w-72 max-w-[calc(100vw-2.5rem)] rounded-xl border border-slate-200 bg-white p-4 shadow-lg" role="status" aria-live="polite">
        <p className="text-xs font-semibold text-slate-800">{label}</p>
        {activity.project && <p className="mt-1.5 break-all text-[11px] text-slate-400">{activity.project}</p>}
        <p className="mt-3 text-xs leading-5 text-slate-500">{linking ? activity.total ? `${activity.done || 0} of ${activity.total} code files checked.` : "Preparing candidate files..." : activity.kind === "change" ? `${activity.checked || 0} trace links checked.` : "An analysis is using the AI model."}</p>
        {linking && activity.requirements?.length > 0 && <p className="mt-2 break-all text-[11px] text-slate-500">{activity.requirements.join(", ")}</p>}
        {progress != null && <div role="progressbar" aria-label="Files checked" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} className="mt-3 h-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${progress}%` }} /></div>}
        {activity.started && <p className="mt-3 text-[10px] text-slate-400">{duration(activity.started)} elapsed</p>}
      </div>
    </details>
  );
}

const pill = (ok, text, warn) => (
  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${ok ? "bg-emerald-50 text-emerald-600" : warn ? "bg-amber-50 text-amber-600" : "bg-red-50 text-red-600"}`}>{text}</span>
);

/** Neo4j / AI model / Redis status, polled. */
export function ServicesBar() {
  const { data } = useApi("/api/health", { pollMs: 10000 });
  if (!data) return null;
  return (
    <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-[12px] text-slate-600 shadow-sm">
      <span className="font-semibold text-slate-700">Services</span>
      <span className="flex items-center gap-2">Knowledge graph {pill(data.neo4j.connected, "connected")}</span>
      <span className="flex items-center gap-2">AI model {pill(data.llm.reachable, data.llm.model || "ready")}</span>
      <span className="flex items-center gap-2">Messages to C3 (Redis) {pill(data.redis.reachable, "connected", true)}</span>
      {!data.neo4j.connected && <span className="text-red-600">Start Neo4j Desktop; this page reconnects by itself.</span>}
      {!data.demo.allowed && <span className="text-amber-600">{data.demo.reason}</span>}
    </div>
  );
}
