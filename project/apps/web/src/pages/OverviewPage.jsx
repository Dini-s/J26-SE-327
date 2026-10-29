import { Activity, ArrowRight, FileCheck2, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { qualityApi } from "../services/qualityApi";
import { Badge, Breakdown, DataState, Empty, Metric, PageHeader, Panel, RequirementLink } from "../component/quality/QualityUI";
import { number, percent, score } from "../services/qualityPresentation";
import { useQualityData } from "../services/useQualityData";

export default function OverviewPage() {
  const { data, loading, error, refresh } = useQualityData(qualityApi.getOverview);
  return <div className="qi-page">
    <PageHeader title="Quality & Testing Intelligence Overview" description="Requirement-centric evidence coverage, execution confirmation, and quality findings." />
    <DataState loading={loading} error={error} retry={refresh} />
    {data && !loading && !error && <>
      <div className="qi-metrics">
        <Metric icon={ShieldCheck} label="Evidence coverage · RVC" value={data.total_rvus ? percent(data.overall_rvc) : "—"} detail={`${number(data.adequate_rvus)} adequate checks out of ${number(data.total_rvus)} total checks`} />
        <Metric icon={FileCheck2} label="Fully validated requirements" value={`${number(data.adequately_validated_requirements)} / ${number(data.total_requirements)}`} detail="Every check has adequate evidence and qualifying execution confirmation." tone="blue" />
        <Metric icon={Activity} label="Requirements needing validation work" value={number((data.partial_requirements || 0) + (data.inadequate_requirements || 0))} detail={`${number(data.partial_requirements)} partially validated · ${number(data.inadequate_requirements)} without validation support · ${number(data.not_assessed_requirements)} not assessed`} tone="amber" />
        <Metric icon={Activity} label="Average evidence score · RVES" value={score(data.avg_rves)} detail="Experimental composite · 0–1 scale" tone="blue" />
      </div>
      <div className="qi-analysis-caption"><span>{number(data.validated_rvus)} checks execution-confirmed / {number(data.total_supported_rvus)} supported checks</span>{data.generated_at && <span>Last analysis: {new Date(data.generated_at).toLocaleString()}</span>}</div>
      <div className="qi-grid two">
        <Panel title="Coverage over time" description="Saved analysis runs on a 0–100% scale.">
          {(data.history || []).length < 2 ? <Empty title="Your baseline is ready">Run another analysis after updating evidence to compare coverage over time. No trend is inferred from a single snapshot.</Empty> : <TrendChart history={data.history} />}
        </Panel>
      <Panel title="Requirements to review first" description="The priority list returned by the latest analysis." action={<Link className="qi-link" to="/quality/requirements">All requirements<ArrowRight size={15} /></Link>}>
        <div className="qi-table-scroll"><table className="qi-table"><thead><tr><th scope="col">Requirement</th><th scope="col">Type</th><th scope="col">Evidence coverage</th><th scope="col">Validation status</th></tr></thead><tbody>{(data.priority_attention || []).slice(0, 4).map((item) => <tr key={item.requirement_id}><td><RequirementLink id={item.requirement_id} /><span className="qi-cell-title">{item.title}</span></td><td><Badge value={item.type} /></td><td>{percent(item.rvc_percent)}<small>{item.adequate_rvus} of {item.total_rvus} checks adequate</small></td><td><Badge value={item.status} requirement /></td></tr>)}</tbody></table></div>
        {!data.priority_attention?.length && <Empty title="No priority requirements returned">Review the complete requirements list for individual coverage and status.</Empty>}
      </Panel>
      </div>
      <div className="qi-grid two">
        <Panel title="Where evidence falls short" description="Generated findings by gap type. One check may have multiple findings.">
          {Object.keys(data.gap_distribution || {}).length ? <Breakdown rows={Object.entries(data.gap_distribution).map(([label, value]) => ({ label: label.toLowerCase().replaceAll("_", " "), value, tone: "amber" }))} /> : <Empty title="No generated findings">Run quality analysis to generate findings from the available evidence.</Empty>}
        </Panel>
      <Panel title="Findings that need attention" description="Leading findings from the analysis. Open a requirement to review all its gaps.">
        <div className="qi-findings">{(data.top_validation_details || []).slice(0, 4).map((item, index) => <article className="qi-finding" key={`${item.requirement_id}-${index}`}><Badge value={item.severity} /><div><p>{item.issue}</p><RequirementLink id={item.requirement_id} /></div></article>)}</div>
        {!data.top_validation_details?.length && <Empty title="No findings returned">Findings appear here after the analysis identifies evidence gaps.</Empty>}
      </Panel>
      </div>
    </>}
  </div>;
}

function TrendChart({ history }) {
  const values = history.slice(-8);
  const points = (key) => values.map((item, index) => `${36 + index * 568 / (values.length - 1)},${184 - Math.min(100, Math.max(0, Number(item[key]) || 0)) * 1.6}`).join(" ");
  return <div className="qi-chart"><svg viewBox="0 0 640 225" role="img" aria-label="Coverage and execution confirmation across saved analyses">{[0, 25, 50, 75, 100].map((value) => <g key={value}><line x1="36" x2="604" y1={184 - value * 1.6} y2={184 - value * 1.6} stroke="#e6ebf2" /><text x="0" y={188 - value * 1.6}>{value}%</text></g>)}<polyline fill="none" stroke="#6366f1" strokeWidth="3" points={points("overall_rvc")} /><polyline fill="none" stroke="#0d9488" strokeWidth="3" strokeDasharray="6 4" points={points("execution_confirmed_percent")} />{values.map((item, index) => <text key={index} x={36 + index * 568 / (values.length - 1)} y="215" textAnchor="middle">{index + 1}</text>)}</svg><div className="qi-chart-legend"><span><i />Evidence coverage</span><span><i className="teal" />Execution confirmed</span><span>Latest {values.length} runs</span></div><details className="qi-chart-data"><summary>View exact values</summary><table className="qi-table"><thead><tr><th>Analysis time</th><th>Coverage</th><th>Execution confirmed</th></tr></thead><tbody>{values.map((item, index) => <tr key={index}><td>{item.generated_at ? new Date(item.generated_at).toLocaleString() : `Run ${index + 1}`}</td><td>{percent(item.overall_rvc)}</td><td>{percent(item.execution_confirmed_percent)}</td></tr>)}</tbody></table></details></div>;
}
