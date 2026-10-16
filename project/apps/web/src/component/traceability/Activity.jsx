import { Loader2 } from "lucide-react";
import { useApi } from "../../api/c4";

const duration = (iso) => {
  if (!iso) return "";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
};

export function ActivityBanner({ activity }) {
  if (!activity || activity.state === "idle") return null;
  let title = "Running";
  let sub = activity.state === "external" ? "A run started outside this page is using the AI model." : "Starting up...";
  let progress = 15;
  if (activity.kind === "link") {
    title = `Linking ${(activity.requirements || []).join(", ")}${activity.project ? ` (${activity.project})` : ""}`;
    sub = activity.total ? `The AI has checked ${activity.done} of ${activity.total} code files, ${duration(activity.started)} so far` : `Shortlisting code files, ${duration(activity.started)}`;
    progress = activity.total ? (100 * activity.done) / activity.total : 0;
  } else if (activity.kind === "change") {
    title = activity.trigger === "monitor" ? `Scanning the links of ${activity.project || "the project"} for drift` : `Re-checking the links of ${(activity.files || []).join(", ") || "the changed file"}`;
    sub = `${activity.checked} link(s) checked, ${duration(activity.started)} so far`;
    progress = 40;
  }
  return (
    <div className="mb-5 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
      <Loader2 size={18} className="animate-spin text-blue-600" />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{title}</p>
        <p className="text-[13px] opacity-80">{sub}</p>
      </div>
      <div className="hidden h-1.5 w-40 overflow-hidden rounded-full bg-blue-100 sm:block">
        <div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
    </div>
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
