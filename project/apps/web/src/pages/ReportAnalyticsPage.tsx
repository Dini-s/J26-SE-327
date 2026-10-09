import type { ReactNode } from "react";

import {
  BarChart3,
  CheckCircle2,
  Download,
  FileText,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { useEffect, useMemo, useState } from "react";

import { Link } from "react-router-dom";

import { ErrorPanel, LoadingPanel, StatusPill } from "../components/UI";

import {
  getEvidence,
  getOverview,
  getRequirements,
} from "../services/qualityApi";

import type {
  OverviewStats,
  Requirement,
  ValidationEvidence,
} from "../types/quality";

export function ReportsAnalyticsPage() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);

  const [requirements, setRequirements] = useState<Requirement[]>([]);

  const [evidence, setEvidence] = useState<ValidationEvidence[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [overviewData, requirementData, evidenceData] = await Promise.all(
          [getOverview(), getRequirements(), getEvidence()],
        );

        setOverview(overviewData);

        setRequirements(requirementData);

        setEvidence(evidenceData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  const automated = useMemo(
    () => evidence.filter((item) => item.evidence_type === "AUTOMATED_TEST"),
    [evidence],
  );

  const pass = automated.filter(
    (item) => item.execution_status === "PASS",
  ).length;

  const skipped = automated.filter(
    (item) => item.execution_status === "SKIPPED",
  ).length;

  const unresolved = automated.filter((item) => !item.execution_status).length;

  if (loading) {
    return <LoadingPanel message="Loading QA reports…" />;
  }

  if (error || !overview) {
    return <ErrorPanel message={error ?? "Reports unavailable."} />;
  }

  return (
    <>
      <div className="page-title-row">
        <div>
          <h1>QA Reports & Analytics</h1>

          <p>
            Comprehensive quality analysis across requirements, evidence and
            test assets.
          </p>
        </div>

        <button className="primary-button" type="button" disabled>
          <Download size={17} />
          Export Report
        </button>
      </div>

      <section className="report-summary-grid">
        <SummaryBox
          title="Evidence Summary"
          icon={<FileText size={18} />}
          rows={[
            ["Total Evidence Items", String(overview.evidence_items)],
            ["Automated Test Artifacts", String(overview.automated_tests)],
            ["Manual QA Evidence", String(overview.manual_tests)],
            ["Performance Evidence", String(overview.performance_evidence)],
          ]}
        />

        <SummaryBox
          title="Test Execution Summary"
          icon={<CheckCircle2 size={18} />}
          rows={[
            ["Passed Automated Tests", String(pass)],
            ["Skipped Automated Tests", String(skipped)],
            ["Execution Mapping Unresolved", String(unresolved)],
            ["Total Automated Tests", String(automated.length)],
          ]}
        />

        <SummaryBox
          title="Revalidation Summary"
          icon={<RefreshCw size={18} />}
          rows={[
            ["Reusable", "—"],
            ["Modification Required", "—"],
            ["Outdated", "—"],
            ["New Evidence Required", "—"],
          ]}
        />

        <SummaryBox
          title="AI Recommendations Summary"
          icon={<Sparkles size={18} />}
          rows={[
            ["Total Recommendations", "—"],
            ["Critical", "—"],
            ["Important", "—"],
            ["Informational", "—"],
          ]}
        />
      </section>

      <article className="surface-card reports-table-card">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Requirement ID</th>

                <th>Requirement Title</th>

                <th>Type</th>
                <th>RVC</th>
                <th>RVES</th>
                <th>Adequacy</th>

                <th>Test Quality</th>

                <th>Revalidation</th>

                <th>AI Recommendation</th>
              </tr>
            </thead>

            <tbody>
              {requirements.slice(0, 10).map((item) => (
                <tr key={item.requirement_id}>
                  <td>
                    <Link
                      className="link-cell"
                      to={`/quality/requirements/` + item.requirement_id}
                    >
                      {item.requirement_id}
                    </Link>
                  </td>

                  <td>{item.title}</td>

                  <td>
                    {item.type === "FUNCTIONAL" ? "Functional" : item.subtype}
                  </td>

                  <td>—</td>
                  <td>—</td>

                  <td>
                    <StatusPill tone="neutral">Pending</StatusPill>
                  </td>

                  <td>Evidence discovery ready</td>

                  <td>—</td>

                  <td>Pending gap analysis</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <section className="report-bottom-grid">
        <article className="surface-card report-insight">
          <BarChart3 size={22} />

          <div>
            <h3>Current Evidence Insight</h3>

            <p>
              {overview.evidence_items} normalized evidence records are
              available for retrieval and later adequacy assessment.
            </p>
          </div>
        </article>

        <article className="surface-card report-insight">
          <RefreshCw size={22} />

          <div>
            <h3>Revalidation Guidance</h3>

            <p>
              Revalidation metrics remain empty until controlled change analysis
              or later C4 integration.
            </p>
          </div>
        </article>

        <article className="surface-card report-insight">
          <ShieldAlert size={22} />

          <div>
            <h3>Risk Areas Identified</h3>

            <p>
              Risk currently comes from the requirement dataset. Validation risk
              will be added only after adequacy reasoning.
            </p>
          </div>
        </article>

        <article className="surface-card report-info">
          <h3>Report Information</h3>

          <Info
            label="Total Requirements"
            value={String(overview.requirements)}
          />

          <Info label="Analysis Scope" value="Standalone Component 3" />

          <Info
            label="Data Source"
            value="Curated requirements + PetClinic QA evidence"
          />

          <Info label="Status" value="Evidence discovery foundation" />
        </article>
      </section>
    </>
  );
}

function SummaryBox({
  title,
  icon,
  rows,
}: {
  title: string;
  icon: ReactNode;
  rows: [string, string][];
}) {
  return (
    <article className="surface-card summary-box">
      <h3>
        {icon}
        {title}
      </h3>

      {rows.map(([label, value]) => (
        <div className="summary-box-row" key={label}>
          <span>{label}</span>

          <strong>{value}</strong>
        </div>
      ))}
    </article>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="report-info-row">
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}
