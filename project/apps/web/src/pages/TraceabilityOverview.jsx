import { useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Download, FileText, Link2, Plus, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { useApi, useProject } from "../api/c4";
import { Button, PageHeader, Ring, Tabs, Callout } from "../component/traceability/ui";
import LinksTable from "../component/traceability/LinksTable";
import { CompletenessPanel, DecayPanel, PipelineStrip, SelfCheckPanel } from "../component/traceability/Panels";
import { EvaluationPanel, EvidencePanel, RerankerPanel } from "../component/traceability/EvaluationPanel";

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
  const covered = Math.max(0, (data?.requirements ?? 0) - orphanCount);
  const coverage = data?.requirements ? Math.round((covered / data.requirements) * 100) : null;
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

      <section className="c4-bento" aria-label="Project summary">
        <div className="c4-bento-main">
          <div className="c4-bento-head">
            <div className="min-w-0">
              <p className="trace-eyebrow">CURRENT PROJECT</p>
              <h2>{project || "Select a project"}</h2>
            </div>
            <div className="c4-bento-actions">
              <Link to={primaryAction.to}><Button disabled={primaryAction.to === "#"}><ActionIcon size={15} />{primaryAction.label}<ArrowRight size={14} /></Button></Link>
              <Link className="trace-secondary-action" to="/traceability/graph">View graph</Link>
            </div>
          </div>
          <div className="c4-coverage">
            <Ring value={coverage ?? 0} loading={loading} label="coverage %" size={128} stroke={11} />
            <div className="c4-coverage-copy">
              <p className="c4-coverage-title">Requirement coverage</p>
              <p className="c4-coverage-text">{loading ? "Loading…" : `${covered} of ${data?.requirements ?? 0} requirements have at least one approved link to code.`}</p>
              <dl className="c4-coverage-facts">
                <div><dt>Score</dt><dd>{mean == null ? "—" : `${Math.round(mean)}/100`}</dd></div>
                <div><dt>Unlinked</dt><dd>{loading ? "—" : orphanCount}</dd></div>
                <div><dt>Deferred</dt><dd>{totals.deferred ?? 0}</dd></div>
                <div><dt>Rejected</dt><dd>{totals.rejected ?? 0}</dd></div>
              </dl>
            </div>
          </div>
        </div>
        <div className="c4-bento-tiles">
          {[
            ["Requirements", data?.requirements, "neutral", "What the project must satisfy", FileText, null],
            ["Approved", verified, "good", "Automatic or human-approved", CheckCircle2, verified],
            ["Needs review", pending, "warn", "AI candidates without a decision", AlertTriangle, pending],
            ["Broken", decayed, "bad", "Code changed; inspect the history", ShieldAlert, decayed],
          ].map(([label, value, tone, hint, Icon, share]) => (
            <div key={label} className={`c4-tile ${tone}`}>
              <div className="c4-tile-top"><span className="c4-tile-icon"><Icon size={16} strokeWidth={2} /></span><p>{label}</p></div>
              <p className="c4-tile-value">{loading ? "—" : value ?? 0}</p>
              <small>{hint}</small>
              {share != null && <div className="c4-tile-bar" title={`${share} of ${all.length} links`}><span style={{ width: `${all.length ? Math.round((share / all.length) * 100) : 0}%` }} /></div>}
            </div>
          ))}
        </div>
      </section>

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
              <EvaluationPanel results={results.data} targets={analysis.data?.evidence?.targets} pending={analysis.data?.evidence?.pending} />
              <EvidencePanel evidence={analysis.data?.evidence} />
              <RerankerPanel analysis={analysis.data} />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TraceabilityOverview;
