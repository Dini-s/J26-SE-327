import { useState } from "react";
import { CheckCheck, ChevronLeft, ChevronRight, Download, Files, GitCompareArrows, ListChecks, Search } from "lucide-react";
import { qualityApi } from "../services/qualityApi";
import { Badge, Coverage, DataState, Empty, PageHeader, Panel, RequirementLink } from "../component/quality/QualityUI";
import { downloadJson, number, score } from "../services/qualityPresentation";
import { useQualityData } from "../services/useQualityData";

export default function ReportsAnalyticsPage() {
  const { data, error, loading, refresh } = useQualityData(qualityApi.getReports);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);
  const root = data?.reports || data || {};
  const evidence = root.evidence_summary || {};
  const execution = root.execution_summary || {};
  const candidate = root.candidate_quality_summary || {};
  const recommendations = root.recommendation_summary || {};
  const changes = data?.revalidation_summary || root.revalidation_summary || {};
  const requirements = data?.requirements || root.requirements || [];
  const filtered = requirements.filter((item) => `${item.requirement_id} ${item.title}`.toLowerCase().includes(search.toLowerCase()));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * 10, current * 10);
  const passed = (execution.automated_pass || 0) + (execution.performance_pass || 0) + (execution.manual_pass || 0);
  const exportReport = async () => {
    setExporting(true); setExportError("");
    try { downloadJson(await qualityApi.exportSummary(), "quality-intelligence-report.json"); }
    catch (reason) { setExportError(reason.message); }
    finally { setExporting(false); }
  };
  return <div className="qi-page"><PageHeader title="QA Reports & Analytics" description="A transparent view of evidence assets, recorded execution results, and requirement change impact."><button className="qi-button primary" onClick={exportReport} disabled={loading || exporting || !data}><Download size={16} />{exporting ? "Exporting…" : "Export full report"}</button></PageHeader>
    {exportError && <div className="qi-notice error" role="alert">{exportError}</div>}
    <DataState loading={loading} error={error} retry={refresh} />
    {data && !loading && !error && <>
      <div className="qi-report-summaries"><SummaryCard title="Evidence Summary" icon={Files} rows={[["Evidence assets", evidence.total_evidence_items], ["Strong candidate matches", candidate.strong, "good"], ["Moderate candidate matches", candidate.moderate, "warn"], ["Weak candidate matches", candidate.weak, "bad"]]} note="Candidate counts are evidence-to-check matches, not unique assets." /><SummaryCard title="Execution Summary" icon={CheckCheck} rows={[["Recorded passing results", passed, "good"], ["Recorded failing results", (execution.automated_fail || 0) + (execution.performance_fail || 0) + (execution.manual_fail || 0), "bad"], ["Skipped results", (execution.automated_skipped || 0) + (execution.performance_skipped || 0) + (execution.manual_skipped || 0), "warn"], ["Automated results without a link", execution.automated_unmapped]]} note="Available counts only. Controlled results may be included." /><SummaryCard title="Revalidation Summary" icon={GitCompareArrows} rows={[["Change cases", changes.change_cases], ["Reusable evidence", changes.reusable, "good"], ["Needs modification", changes.modification_required, "warn"], ["Outdated evidence", changes.outdated, "bad"], ["New evidence required", changes.new_evidence_required]]} /><SummaryCard title="Recommended Actions" icon={ListChecks} rows={[["Total recommendations", recommendations.total], ["Critical", recommendations.critical, "bad"], ["Important", recommendations.important, "warn"], ["Informational", recommendations.informational]]} /></div>
      <Panel title="Requirement-level analysis" description={`${filtered.length} requirements shown. Open a requirement to inspect its evidence and change cases.`} action={<label className="qi-search"><Search size={17} /><input aria-label="Search report requirements" placeholder="Search requirements" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /></label>}><div className="qi-table-scroll"><table className="qi-table"><thead><tr><th>Requirement</th><th>Type</th><th>Evidence coverage</th><th>Execution confirmed</th><th>Evidence score</th><th>Validation status</th></tr></thead><tbody>{visible.map((item) => <tr key={item.requirement_id}><td><RequirementLink id={item.requirement_id} /><span className="qi-cell-title">{item.title}</span></td><td><Badge value={item.type} /></td><td><Coverage value={item.rvc_percent} available={item.total_rvus > 0} /><small>{item.adequate_rvus} / {item.total_rvus} checks adequate</small></td><td>{item.validated_rvus} / {item.supported_rvus}<small>supported checks</small></td><td>{item.status === "NOT_ASSESSED" ? "Not assessed" : score(item.rves)}<small>Experimental · RVES</small></td><td><Badge value={item.status} requirement /><small>{number(item.not_assessed_rvus)} checks not assessed</small></td></tr>)}</tbody></table></div>{!filtered.length && <Empty title="No matching requirements">Try another search or run an analysis to populate the report.</Empty>}<div className="qi-pagination"><span>{filtered.length ? `${(current - 1) * 10 + 1}–${Math.min(current * 10, filtered.length)} of ${filtered.length}` : "0 results"}</span><div><button className="qi-icon-button" aria-label="Previous report page" disabled={current <= 1} onClick={() => setPage(current - 1)}><ChevronLeft size={17} /></button><span>Page {current} of {pages}</span><button className="qi-icon-button" aria-label="Next report page" disabled={current >= pages} onClick={() => setPage(current + 1)}><ChevronRight size={17} /></button></div></div></Panel>
      <div className="qi-grid four"><Panel title="Recommended Action Insights"><ul className="qi-clean-list"><li>{number(recommendations.critical)} critical recommendations need priority review.</li><li>{number(recommendations.important)} recommendations are classified as important.</li><li>Open a requirement to see its grounded evidence findings and next actions.</li></ul></Panel><Panel title="Revalidation Guidance"><ul className="qi-clean-list"><li>{number(changes.change_cases)} change contexts analyzed.</li><li>{number(changes.modification_required)} evidence assets need modification.</li><li>{number(changes.new_evidence_required)} new evidence items are required.</li></ul></Panel><Panel title="Risk Areas"><ul className="qi-clean-list"><li>Prioritize high-risk requirements with low evidence coverage.</li><li>Review adequate evidence without qualifying execution.</li><li>Unsupported checks need specialist assessment.</li></ul></Panel>
      <Panel title="Report context" description="Use the exported report to retain the underlying analysis and methodology."><dl className="qi-report-context"><div><dt>Generated</dt><dd>{root.report_information?.generated_at || root.generated_at ? new Date(root.report_information?.generated_at || root.generated_at).toLocaleString() : "No generation time supplied"}</dd></div><div><dt>Scope</dt><dd>{root.report_information?.analysis_scope || `${requirements.length} requirements in the current analysis`}</dd></div><div><dt>Data sources</dt><dd>{root.report_information?.data_source || "Requirements, derived validation checks, evidence assets and execution results"}</dd></div></dl></Panel>
      </div>

    </>}
  </div>;
}

function SummaryCard({ title, icon: Icon, rows, note }) {
  return <article className="qi-panel qi-summary-card"><h2><Icon size={17} />{title}</h2><dl>{rows.map(([label, value, tone]) => <div key={label}><dt><span className={`qi-summary-dot ${tone || ""}`} />{label}</dt><dd className={tone ? `qi-summary-${tone}` : ""}>{number(value)}</dd></div>)}</dl>{note && <p>{note}</p>}</article>;
}
