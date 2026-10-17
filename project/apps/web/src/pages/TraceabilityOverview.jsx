import { useState } from "react";
import { Activity, Download, FileText, FolderGit2, GitBranch, ShieldAlert, TriangleAlert } from "lucide-react";
import { useApi, useProject } from "../api/c4";
import { PageHeader, Ring, Metric, Tabs, Callout } from "../component/traceability/ui";
import LinksTable from "../component/traceability/LinksTable";
import { CompletenessPanel, DecayPanel, PipelineStrip, SelfCheckPanel } from "../component/traceability/Panels";
import { EvaluationPanel, RerankerPanel } from "../component/traceability/EvaluationPanel";

const TraceabilityOverview = () => {
  const { project, error: projectsError } = useProject();
  const enc = project ? encodeURIComponent(project) : null;
  const links = useApi(enc ? `/api/links?project=${enc}` : null);
  const completeness = useApi(enc ? `/api/completeness?project=${enc}` : null);
  const results = useApi("/api/results");
  const analysis = useApi("/api/analysis");
  const selfcheck = useApi(enc ? `/api/selfcheck?project=${enc}` : null);
  const [tab, setTab] = useState("links");

  const data = links.data;
  const all = data?.links ?? [];
  const verified = all.filter((l) => l.status !== "decayed").length;
  const decayed = all.length - verified;
  const loading = !data;
  const mean = completeness.data?.mean;

  return (
    <div className="mx-auto w-full max-w-[1400px] pb-8">
      <PageHeader
        page="Overview"
        title="Traceability Intelligence"
        description="Links each requirement to the code that implements it, has an AI model check every link, and keeps re-checking as the project changes."
        apiError={projectsError || links.error}
      >
        {enc && (
          <div className="flex items-center gap-2">
            {[["matrix", "Matrix CSV"], ["links", "Links CSV"], ["report", "Report JSON"]].map(([kind, label]) => (
              <a key={kind} href={`/api/export?project=${enc}&kind=${kind}`} download className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-[12px] font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-600">
                <Download size={13} /> {label}
              </a>
            ))}
          </div>
        )}
      </PageHeader>

      <section className="flex flex-col gap-5 rounded-2xl border border-slate-200/80 bg-gradient-to-r from-indigo-50/60 via-white to-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] xl:flex-row xl:items-center">
        <div className="flex items-center gap-4 xl:w-[290px] xl:shrink-0">
          <Ring value={mean} loading={mean == null} label="of 100" size={96} stroke={9} />
          <div>
            <p className="text-[14px] font-semibold text-slate-900">Traceability score</p>
            <p className="mt-1 text-[12px] leading-snug text-slate-500">Mean confidence of the verified links. A requirement with no link counts as 0.</p>
          </div>
        </div>
        <div className="grid flex-1 grid-cols-2 gap-x-2 gap-y-4 border-slate-200 sm:grid-cols-3 xl:grid-cols-6 xl:border-l xl:pl-5">
          <Metric label="Requirements" value={data?.requirements} icon={FileText} tone="green" loading={loading} />
          <Metric label="Code files" value={data?.codeEntities} icon={FolderGit2} tone="indigo" loading={loading} />
          <Metric label="Verified" value={verified} icon={GitBranch} tone="indigo" loading={loading} />
          <Metric label="Broken" value={decayed} icon={TriangleAlert} tone={decayed ? "red" : "slate"} loading={loading} />
          <Metric label="Orphans" value={data?.orphans.length} icon={ShieldAlert} tone={data?.orphans.length ? "amber" : "slate"} loading={loading} />
          <Metric label="Avg confidence" value={all.length ? (all.reduce((a, l) => a + (l.confidence ?? 0), 0) / all.length).toFixed(2) : "-"} icon={Activity} tone="green" loading={loading} />
        </div>
      </section>

      <div className="mt-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { id: "links", label: "Trace links", count: all.length },
            { id: "health", label: "Health", count: decayed || undefined },
            { id: "pipeline", label: "How it works" },
            { id: "evidence", label: "Measured results" },
          ]}
        />
        <div className="mt-4 max-h-[calc(100vh-330px)] min-h-[320px] space-y-5 overflow-auto pb-2 pr-1">
          {tab === "links" && <LinksTable links={all} />}
          {tab === "health" && (
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <DecayPanel flags={data?.decayFlags ?? []} />
              <CompletenessPanel completeness={completeness.data} />
              <div className="xl:col-span-2"><SelfCheckPanel report={selfcheck.data} /></div>
            </div>
          )}
          {tab === "pipeline" && <PipelineStrip />}
          {tab === "evidence" && (
            <>
              <Callout tone="warn">These are honest measurements on small samples. Several targets are not met yet; the notes under each number explain why.</Callout>
              <EvaluationPanel results={results.data} />
              <RerankerPanel analysis={analysis.data} />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TraceabilityOverview;
