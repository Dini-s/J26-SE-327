import { useMemo, useState } from "react";
import { Activity, FileWarning, Gauge, Percent, Search } from "lucide-react";
import { useApi, useProject } from "../api/c4";
import { Card, Chip, ConfBar, EmptyState, FileBadge, Metric, PageHeader, Segmented, Tabs } from "../component/traceability/ui";
import { BarChart, Timeline } from "../component/traceability/charts";
import { shortName } from "../component/traceability/utils";

const SEC_PER_CHECK = 52; // measured LLM time per link on the CPU-only server

function Insights({ a }) {
  return (
    <div className="space-y-5">
      <section className="grid grid-cols-2 gap-5 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] lg:grid-cols-4">
        <Metric label="Requirement coverage" value={`${Math.round(a.coverage * 100)}%`} icon={Percent} tone="indigo" />
        <Metric label="Mean confidence" value={a.meanConfidence.toFixed(2)} icon={Gauge} tone="green" />
        <Metric label="Verified links" value={a.verifiedLinks} icon={Activity} tone="indigo" />
        <Metric label="Decay events" value={a.decayEvents} icon={FileWarning} tone={a.decayEvents ? "red" : "slate"} />
      </section>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="Link confidence" description="How sure the AI was about each verified link.">
          <BarChart items={a.confidenceHistogram} tone="indigo" />
        </Card>
        <Card title="Links per requirement" description="Requirements with 0 links are orphans.">
          <BarChart items={a.linksPerRequirement} tone="green" />
        </Card>
        <Card title="Links over time" description="Cumulative verified links; red = decay events that day.">
          <Timeline points={a.timeline} />
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="Change hotspots" description="Files the most requirements depend on. Changing them has the widest impact." flush>
          <RankList rows={a.hotspots} value={(r) => `${r.requirements} req`} />
        </Card>
        <Card title="Unstable files" description="Files whose links decayed most often." flush>
          {a.unstableFiles.length === 0 ? <div className="px-5 pb-5"><EmptyState title="No decay yet" /></div> : <RankList rows={a.unstableFiles} value={(r) => `${r.decays}x`} tone="red" />}
        </Card>
        <Card title="Weakest links" description="Lowest-confidence verified links: review these first." flush>
          <ul className="divide-y divide-slate-100">
            {a.weakestLinks.slice(0, 6).map((l) => (
              <li key={`${l.requirement}${l.code}`} className="flex items-center justify-between gap-3 px-5 py-2.5 text-[13px]">
                <span className="min-w-0">
                  <span className="block truncate font-medium text-slate-800">{l.requirement}</span>
                  <span className="block truncate text-[12px] text-slate-500">{l.name}</span>
                </span>
                <ConfBar value={l.confidence} />
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function RankList({ rows, value, tone }) {
  return (
    <ul className="divide-y divide-slate-100">
      {rows.slice(0, 6).map((r, i) => (
        <li key={r.code} className="flex items-center gap-3 px-5 py-2.5 text-[13px]">
          <span className="w-4 text-[12px] tabular-nums text-slate-400">{i + 1}</span>
          <FileBadge name={r.name} />
          <span className="min-w-0 flex-1 truncate font-medium text-slate-800" title={r.code}>{r.name}</span>
          <Chip tone={tone || "indigo"}>{value(r)}</Chip>
        </li>
      ))}
    </ul>
  );
}

/** "If this changes, what is affected?" answered from the links already loaded. */
function Impact({ links }) {
  const [mode, setMode] = useState("code");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState(null);

  const keyOf = (l) => (mode === "code" ? l.code : l.requirement);
  const options = useMemo(() => {
    const counts = new Map();
    links.forEach((l) => counts.set(keyOf(l), (counts.get(keyOf(l)) ?? 0) + 1));
    const q = query.trim().toLowerCase();
    return [...counts.entries()]
      .filter(([k]) => !q || k.toLowerCase().includes(q))
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 40);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [links, mode, query]);

  const selected = options.find(([k]) => k === picked)?.[0] ?? picked;
  const affected = selected ? links.filter((l) => keyOf(l) === selected) : [];
  const seconds = affected.length * SEC_PER_CHECK;

  return (
    <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
      <Card title="Pick something" description="See what depends on it." flush>
        <div className="space-y-3 px-5 pb-3">
          <Segmented value={mode} onChange={(m) => { setMode(m); setPicked(null); }} items={[{ id: "code", label: "A code file" }, { id: "req", label: "A requirement" }]} />
          <label className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-slate-400 focus-within:border-indigo-300">
            <Search size={14} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search" className="w-full bg-transparent text-[13px] text-slate-800 outline-none placeholder:text-slate-400" />
          </label>
        </div>
        <ul className="max-h-[calc(100vh-420px)] min-h-[200px] divide-y divide-slate-100 overflow-auto border-t border-slate-100">
          {options.map(([k, n]) => (
            <li key={k}>
              <button type="button" onClick={() => setPicked(k)} className={`flex w-full items-center justify-between gap-2 px-5 py-2.5 text-left text-[13px] transition hover:bg-slate-50 ${k === selected ? "bg-indigo-50/60 font-semibold text-indigo-700" : "text-slate-700"}`}>
                <span className="truncate" title={k}>{mode === "code" ? shortName(k) : k}</span>
                <Chip>{n}</Chip>
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={selected ? `Impact of ${mode === "code" ? shortName(selected) : selected}` : "Impact"}>
        {!selected ? (
          <EmptyState title="Choose a file or requirement">If a file changes, every requirement linked to it must be re-checked. This shows which ones and roughly how long that takes.</EmptyState>
        ) : (
          <>
            <div className="mb-4 grid grid-cols-3 gap-3">
              <Mini label={mode === "code" ? "Requirements affected" : "Files involved"} value={affected.length} />
              <Mini label="Already broken" value={affected.filter((l) => l.status === "decayed").length} tone="red" />
              <Mini label="Re-check time" value={seconds < 90 ? `${seconds} s` : `~${Math.round(seconds / 60)} min`} />
            </div>
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
              {affected.map((l) => (
                <li key={`${l.requirement}${l.code}`} className="flex items-center gap-3 px-4 py-3 text-[13px]">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900">{mode === "code" ? l.requirement : shortName(l.code)}</p>
                    <p className="truncate text-[12px] text-slate-500">{mode === "code" ? l.requirementText : l.reason}</p>
                  </div>
                  <ConfBar value={l.confidence} tone={l.status === "decayed" ? "red" : undefined} />
                  <Chip tone={l.status === "decayed" ? "red" : "green"} dot>{l.status === "decayed" ? "broken" : "verified"}</Chip>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[12px] text-slate-400">Time estimate: {SEC_PER_CHECK} s per link, measured on the CPU-only server.</p>
          </>
        )}
      </Card>
    </div>
  );
}

function Mini({ label, value, tone }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3">
      <p className="text-[12px] text-slate-500">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums ${tone === "red" && value ? "text-red-600" : "text-slate-900"}`}>{value}</p>
    </div>
  );
}

const TraceabilityAnalytics = () => {
  const { project, error: projectsError } = useProject();
  const enc = project ? encodeURIComponent(project) : null;
  const analytics = useApi(enc ? `/api/analytics?project=${enc}` : null);
  const links = useApi(enc ? `/api/links?project=${enc}` : null);
  const [tab, setTab] = useState("insights");
  const all = useMemo(() => links.data?.links ?? [], [links.data]);

  return (
    <div className="mx-auto w-full max-w-[1400px] pb-8">
      <PageHeader
        page="Analytics"
        title="Traceability Analytics"
        description="Where the links are strong or weak, which files are risky to change, and what a change would affect."
        apiError={projectsError || analytics.error}
      />
      <Tabs value={tab} onChange={setTab} items={[{ id: "insights", label: "Insights" }, { id: "impact", label: "Impact analysis" }]} />
      <div className="mt-4">
        {tab === "insights" && (analytics.data ? <Insights a={analytics.data} /> : <Card><EmptyState title="Loading analytics..." /></Card>)}
        {tab === "impact" && <Impact links={all} />}
      </div>
    </div>
  );
};

export default TraceabilityAnalytics;
