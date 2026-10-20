import { useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Download, Link2, Plus, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { useApi, useProject } from "../api/c4";
import { Button, PageHeader, Tabs, Callout } from "../component/traceability/ui";
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
  const totals = data?.totals ?? {};
  const verified = totals.verified ?? all.filter((l) => l.status === "verified").length;
  const decayed = totals.decayed ?? all.filter((l) => l.status === "decayed").length;
  const loading = !data;
  const mean = completeness.data?.mean;
  const pending = totals.pending_review ?? all.filter((l) => l.status === "pending_review").length;
  const orphanCount = data?.orphans?.length ?? 0;
  const primaryAction = useMemo(() => {
    if (!data) return { label: "Loading workspace", to: "#", icon: Link2 };
    if (orphanCount) return { label: "Add requirements", to: "/traceability/link", icon: Plus };
    if (!all.length) return { label: "Create trace links", to: "/traceability/link", icon: Link2 };
    if (pending) return { label: "Review candidates", to: "/traceability/labeling", icon: CheckCircle2 };
    if (decayed) return { label: "Inspect broken links", to: "/traceability/changes", icon: ShieldAlert };
    return { label: "Explore trace graph", to: "/traceability/graph", icon: Link2 };
  }, [all.length, data, decayed, orphanCount, pending]);
  const ActionIcon = primaryAction.icon;

  return (
    <div className="mx-auto w-full max-w-[1240px] pb-8">
      <PageHeader
        page="Overview"
        title="Traceability"
        description="A simple answer to one question: can we prove each requirement is connected to the code?"
        apiError={projectsError || links.error}
      >
        {enc && (
          <details className="trace-export-menu">
            <summary><Download size={13} className="mr-1.5 inline" /> Export</summary>
            <div className="trace-export-options">
              {[["matrix", "Matrix CSV"], ["links", "Links CSV"], ["report", "Report JSON"]].map(([kind, label]) => <a key={kind} href={`/api/export?project=${enc}&kind=${kind}`} download><Download size={12} />{label}</a>)}
            </div>
          </details>
        )}
      </PageHeader>

      <section className="trace-hero" aria-label="Traceability workspace">
        <div>
          <p className="trace-eyebrow">CURRENT PROJECT</p>
          <h2>{project || "Select a project"}</h2>
          <p className="trace-hero-copy">Approved links count toward coverage. Candidates wait for review, while broken links are kept as history and sent to change inspection.</p>
        </div>
        <div className="trace-hero-actions">
          <Link to={primaryAction.to}><Button disabled={primaryAction.to === "#"}><ActionIcon size={15} />{primaryAction.label}<ArrowRight size={14} /></Button></Link>
          <Link className="trace-secondary-action" to="/traceability/graph">View graph</Link>
        </div>
      </section>

      <section className="trace-summary" aria-label="Project summary">
        <div className="trace-summary-values">
          {[["Requirements", data?.requirements, "neutral", "What the project must satisfy"], ["Approved", verified, "good", "Counted in coverage"], ["Needs review", pending, "warn", "Waiting for a decision"], ["Broken", decayed, "bad", "Needs change inspection"]].map(([label, value, tone, hint]) => <div key={label} className={`trace-summary-value ${tone}`}><p>{label}</p><p>{loading ? "—" : value}</p><small>{hint}</small></div>)}
        </div>
        <div className="trace-summary-note"><span>Score <b>{mean == null ? "—" : `${Math.round(mean)}/100`}</b></span><span>Deferred <b>{totals.deferred ?? 0}</b></span><span>Rejected <b>{totals.rejected ?? 0}</b></span><span>Unlinked requirements <b>{data?.orphans.length ?? "—"}</b></span></div>
      </section>

      <div className="trace-explain-row">
        <div><span className="trace-explain-icon good"><CheckCircle2 size={16} /></span><div><b>Approved</b><p>Automatic or human-approved links.</p></div></div>
        <div><span className="trace-explain-icon warn"><AlertTriangle size={16} /></span><div><b>Needs review</b><p>AI candidates without a decision.</p></div></div>
        <div><span className="trace-explain-icon bad"><ShieldAlert size={16} /></span><div><b>Broken</b><p>Code changed; inspect the decay history.</p></div></div>
      </div>

      <div className="mt-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { id: "links", label: "Links", count: all.length },
            { id: "health", label: "Health", count: decayed || undefined },
            { id: "pipeline", label: "Pipeline" },
            { id: "evidence", label: "Results" },
          ]}
        />
        <div className="trace-page-content mt-5 min-h-[320px] space-y-5">
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
