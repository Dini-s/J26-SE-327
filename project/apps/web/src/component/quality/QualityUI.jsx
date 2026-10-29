import { AlertCircle, ArrowRight, ArrowUpRight, Info, LoaderCircle, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { humanize, number, percent } from "../../services/qualityPresentation";

export function PageHeader({ eyebrow = "QUALITY INTELLIGENCE", title, description, children }) {
  return <header className="qi-page-header"><div><h1>{eyebrow === "QUALITY INTELLIGENCE" && title.includes("Overview") ? <span className="qi-component-number">3</span> : null}{title}</h1><p>{description}</p></div><div className="qi-actions">{children}</div></header>;
}

export function FocusCard({ icon: Icon = AlertCircle, value, label, detail, to, href, action = "Review now", tone = "amber" }) {
  const content = <><span className="qi-focus-icon"><Icon size={21} /></span><div><span className="qi-focus-label">{label}</span><strong>{value}</strong><p>{detail}</p><span className="qi-focus-action">{action}<ArrowRight size={15} /></span></div></>;
  return to ? <Link className={`qi-focus-card ${tone}`} to={to}>{content}</Link> : <a className={`qi-focus-card ${tone}`} href={href}>{content}</a>;
}

export function CoverageRing({ value, label, detail }) {
  const safeValue = Math.min(100, Math.max(0, Number(value) || 0));
  return <div className="qi-ring-wrap"><div className="qi-ring" style={{ "--coverage": `${safeValue}%` }}><div><strong>{percent(value)}</strong><span>{label}</span></div></div><p>{detail}</p></div>;
}

export function Metric({ icon: Icon = Info, label, value, detail, tone = "indigo", children }) {
  return <article className={`qi-metric qi-tone-${tone}`}><div className="qi-metric-top"><span>{label}</span><span className="qi-metric-icon"><Icon size={19} aria-hidden="true" /></span></div><strong className="qi-metric-value">{value ?? "—"}</strong><p>{detail}</p>{children}</article>;
}

export function Panel({ title, description, action, children, className = "" }) {
  return <section className={`qi-panel ${className}`}><div className="qi-panel-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>{children}</section>;
}

export function Badge({ value, requirement = false }) {
  const good = ["ADEQUATE", "PASS", "VALIDATED", "REUSABLE", "STRONG"].includes(value);
  const bad = ["INADEQUATE", "FAIL", "HIGH", "OUTDATED", "CRITICAL"].includes(value);
  const warn = ["PARTIAL", "MEDIUM", "MODIFICATION_REQUIRED", "BLOCKED", "IMPORTANT"].includes(value);
  return <span className={`qi-badge ${good ? "good" : bad ? "bad" : warn ? "warn" : "neutral"}`}><span aria-hidden="true" />{requirement && value === "ADEQUATE" ? "Fully validated" : requirement && value === "PARTIAL" ? "Partially validated" : requirement && value === "INADEQUATE" ? "No validation support" : humanize(value)}</span>;
}
export function Coverage({ value, available = true }) {
  return <div className="qi-coverage"><strong>{available ? percent(value) : "Not assessable"}</strong><div className="qi-progress" aria-hidden="true"><span style={{ width: `${available ? Math.min(100, Math.max(0, Number(value) || 0)) : 0}%` }} /></div></div>;
}
export function DataState({ loading, error, retry }) {
  if (!loading && !error) return null;
  return <div className={`qi-state ${error ? "qi-error" : ""}`} role={error ? "alert" : "status"}>{error ? <AlertCircle size={28} /> : <LoaderCircle className="qi-spin" size={28} />}<h2>{error ? "We couldn’t load this view" : "Loading quality insights"}</h2><p>{error || "Reading the latest requirements and evidence analysis."}</p>{error && <button className="qi-button" onClick={retry}><RotateCw size={16} />Try again</button>}</div>;
}
export function Empty({ title = "Nothing to show yet", children }) {
  return <div className="qi-empty"><Info size={24} /><h3>{title}</h3><p>{children}</p></div>;
}
export function RequirementLink({ id, children }) {
  return <Link className="qi-link" to={`/quality/requirements/${encodeURIComponent(id)}`}>{children || id}<ArrowUpRight size={14} /></Link>;
}
export function Breakdown({ rows, total }) {
  const denominator = total ?? rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0);
  return <div className="qi-breakdown">{rows.map((row) => <div className="qi-breakdown-row" key={row.label}><div><span>{row.label}</span><strong>{number(row.value)}</strong></div><div className={`qi-progress ${row.tone || ""}`} aria-hidden="true"><span style={{ width: `${denominator ? (Number(row.value) || 0) / denominator * 100 : 0}%` }} /></div>{row.detail && <small>{row.detail}</small>}</div>)}</div>;
}
