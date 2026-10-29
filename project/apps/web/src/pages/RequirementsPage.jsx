import { useMemo, useState } from "react";
import { Activity, ArrowRight, ChevronLeft, ChevronRight, FileText, Search, ShieldCheck, SlidersHorizontal, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { qualityApi } from "../services/qualityApi";
import { Badge, Coverage, DataState, Empty, Metric, PageHeader, Panel, RequirementLink } from "../component/quality/QualityUI";
import { number, percent, score } from "../services/qualityPresentation";
import { useQualityData } from "../services/useQualityData";

const PAGE_SIZE = 8;
export default function RequirementsPage() {
  const { data, error, loading, refresh } = useQualityData(qualityApi.getRequirements);
  const [searchParams, setSearchParams] = useSearchParams();
  const focus = searchParams.get("focus") || "all";
  const [sort, setSort] = useState("priority");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [risk, setRisk] = useState("ALL");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(null);
  const rows = useMemo(() => {
    const filtered = (data || []).filter((item) => matchesFocus(item, focus) && (!search || `${item.requirement_id} ${item.title} ${item.text || ""}`.toLowerCase().includes(search.toLowerCase())) && (type === "ALL" || item.type === type) && (status === "ALL" || item.status === status) && (risk === "ALL" || item.risk === risk));
    return filtered.sort((a, b) => sort === "coverage" ? a.rvc_percent - b.rvc_percent : sort === "name" ? a.title.localeCompare(b.title) : ({ HIGH: 0, MEDIUM: 1, LOW: 2 }[a.risk] ?? 3) - ({ HIGH: 0, MEDIUM: 1, LOW: 2 }[b.risk] ?? 3) || a.rvc_percent - b.rvc_percent);
  }, [data, search, type, status, risk, focus, sort]);
  const selected = rows.find((item) => item.requirement_id === selectedId) || rows[0];
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const totals = (data || []).reduce((sum, row) => ({ checks: sum.checks + row.total_rvus, adequate: sum.adequate + row.adequate_rvus, confirmed: sum.confirmed + row.validated_rvus, supported: sum.supported + row.supported_rvus }), { checks: 0, adequate: 0, confirmed: 0, supported: 0 });
  const filter = (setter) => (event) => { setter(event.target.value); setPage(1); };
  const clear = () => { setSearch(""); setType("ALL"); setStatus("ALL"); setRisk("ALL"); setSearchParams({}); setPage(1); };
  return <div className="qi-page"><PageHeader title="Requirements" description="Find a requirement, understand its evidence coverage, and inspect the checks behind its status." />
    <DataState loading={loading} error={error} retry={refresh} />
    {!loading && !error && <>
      <div className="qi-metrics five"><Metric icon={FileText} label="Total requirements" value={number(data?.length)} detail="Current analysis scope" /><Metric icon={SlidersHorizontal} label="Validation checks · RVUs" value={number(totals.checks)} detail={`${number(totals.supported)} supported checks`} /><Metric icon={ShieldCheck} label="Checks with adequate evidence" value={number(totals.adequate)} detail={`Out of ${number(totals.checks)} checks`} tone="teal" /><Metric icon={ShieldCheck} label="Overall coverage · RVC" value={totals.checks ? percent(totals.adequate / totals.checks * 100) : "—"} detail="Adequate checks ÷ total checks" tone="teal" /><Metric icon={Activity} label="Average evidence score" value={score((data || []).filter((item) => item.status !== "NOT_ASSESSED").length ? (data || []).filter((item) => item.status !== "NOT_ASSESSED").reduce((sum, item) => sum + item.rves, 0) / (data || []).filter((item) => item.status !== "NOT_ASSESSED").length : null)} detail="Experimental RVES · assessed requirements" tone="blue" /></div>
      <div className="qi-workbench" id="requirement-explorer"><Panel title="Requirement explorer" description={`${rows.length} matching requirements · Select a row preview or open a requirement ID.`}>
        <div className="qi-filters">{focus !== "all" && <span className="qi-active-filter">Focused view: {focus.replaceAll("-", " ")}</span>}<label>Sort by<select value={sort} onChange={filter(setSort)}><option value="priority">Risk, then coverage</option><option value="coverage">Lowest coverage</option><option value="name">Requirement title</option></select></label><label className="qi-search"><Search size={17} /><input aria-label="Search requirements" placeholder="Search ID, title or requirement text" value={search} onChange={filter(setSearch)} /></label><label>Type<select value={type} onChange={filter(setType)}><option value="ALL">All types</option><option value="FUNCTIONAL">Functional</option><option value="NON_FUNCTIONAL">Non-functional</option></select></label><label>Validation status<select value={status} onChange={filter(setStatus)}><option value="ALL">All statuses</option><option value="ADEQUATE">Fully validated</option><option value="PARTIAL">Partially validated</option><option value="INADEQUATE">No validation support</option><option value="NOT_ASSESSED">Not assessed</option></select></label><label>Risk<select value={risk} onChange={filter(setRisk)}><option value="ALL">All risks</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select></label>{(search || type !== "ALL" || status !== "ALL" || risk !== "ALL" || focus !== "all") && <button className="qi-button quiet" onClick={clear}><X size={15} />Reset</button>}</div>
        <div className="qi-table-scroll"><table className="qi-table"><thead><tr><th>ID</th><th>Requirement</th><th>Type</th><th>Risk</th><th>Checks</th><th>Adequate</th><th>RVC</th><th>RVES</th><th>Status</th><th>Preview</th></tr></thead><tbody>{visible.map((item) => <tr key={item.requirement_id} className={selected?.requirement_id === item.requirement_id ? "selected" : ""}><td><RequirementLink id={item.requirement_id} /></td><td><span className="qi-cell-title">{item.title}</span></td><td><Badge value={item.type} /></td><td><Badge value={item.risk} /></td><td>{item.total_rvus}</td><td>{item.adequate_rvus}</td><td><Coverage value={item.rvc_percent} available={item.total_rvus > 0} /></td><td>{item.status === "NOT_ASSESSED" ? "—" : Number(item.rves).toFixed(2)}</td><td><Badge value={item.status} requirement /></td><td><button className="qi-icon-button" aria-label={`Preview ${item.requirement_id}`} aria-pressed={selected?.requirement_id === item.requirement_id} onClick={() => setSelectedId(item.requirement_id)}><ArrowRight size={17} /></button></td></tr>)}</tbody></table></div>
        {!rows.length && <Empty title="No requirements match your filters">Try another search or reset the filters to see the complete list.</Empty>}
        <div className="qi-pagination"><span>{rows.length ? `${(current - 1) * PAGE_SIZE + 1}–${Math.min(current * PAGE_SIZE, rows.length)} of ${rows.length}` : "0 results"}</span><div><button className="qi-icon-button" aria-label="Previous page" disabled={current <= 1} onClick={() => setPage(current - 1)}><ChevronLeft size={17} /></button><span>Page {current} of {pages}</span><button className="qi-icon-button" aria-label="Next page" disabled={current >= pages} onClick={() => setPage(current + 1)}><ChevronRight size={17} /></button></div></div>
      </Panel>
      <aside className="qi-preview"><Panel title="Selection Summary" description="A quick look before opening the full evidence review.">{selected ? <><span className="qi-id">{selected.requirement_id}</span><h3>{selected.title}</h3><p className="qi-body-text">{selected.text}</p><div className="qi-inline"><Badge value={selected.type} /><Badge value={selected.status} requirement /></div><dl className="qi-definition-list"><div><dt>Checks with adequate evidence</dt><dd>{selected.adequate_rvus} / {selected.total_rvus}</dd></div><div><dt>Execution-confirmed checks</dt><dd>{selected.validated_rvus} / {selected.supported_rvus} supported</dd></div><div><dt>Evidence score · experimental</dt><dd>{selected.status === "NOT_ASSESSED" ? "Not assessed" : score(selected.rves)}</dd></div><div><dt>Checks not assessed</dt><dd>{number(selected.not_assessed_rvus)}</dd></div><div><dt>Requirement version</dt><dd>{selected.version == null ? "Not supplied" : `v${selected.version}`}</dd></div></dl><Link className="qi-button primary full" to={`/quality/requirements/${encodeURIComponent(selected.requirement_id)}`}>Review evidence<ArrowRight size={16} /></Link></> : <Empty title="No selection">A requirement preview will appear here.</Empty>}</Panel></aside></div>
    </>}
  </div>;
}

function matchesFocus(item, focus) {
  if (focus === "high-risk") return item.risk === "HIGH" && item.status !== "ADEQUATE";
  if (focus === "execution") return item.supported_rvus > item.validated_rvus;
  if (focus === "coverage") return item.supported_rvus > item.adequate_rvus;
  if (focus === "unassessed") return item.not_assessed_rvus > 0;
  return true;
}
