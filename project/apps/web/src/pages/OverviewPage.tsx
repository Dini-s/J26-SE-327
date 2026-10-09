import {
  AlertTriangle,
  CheckSquare2,
  Play,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  Waves,
} from "lucide-react";

import { useEffect, useMemo, useState } from "react";

import { Link } from "react-router-dom";

import {
  ErrorPanel,
  LoadingPanel,
  MetricCard,
  StatusPill,
} from "../components/UI";

import { getOverview, getRequirements } from "../services/qualityApi";

import type { OverviewStats, Requirement } from "../types/quality";

export function OverviewPage() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);

  const [requirements, setRequirements] = useState<Requirement[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);

      const [overviewData, requirementData] = await Promise.all([
        getOverview(),
        getRequirements(),
      ]);

      setOverview(overviewData);

      setRequirements(requirementData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const highRisk = useMemo(
    () => requirements.filter((item) => item.risk === "HIGH").slice(0, 5),
    [requirements],
  );

  if (loading) {
    return <LoadingPanel message="Loading QA intelligence overview…" />;
  }

  if (error || !overview) {
    return <ErrorPanel message={error ?? "Overview unavailable."} />;
  }

  return (
    <>
      <div className="page-title-row">
        <div>
          <div className="title-with-number">
            <span className="title-number">3</span>

            <h1>Quality & Testing Intelligence</h1>
          </div>

          <p>Requirement-centric QA evidence and test adequacy overview</p>
        </div>

        <div className="page-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={() => void load()}
          >
            <RefreshCw size={16} />
            Refresh
          </button>

          <button className="secondary-button" type="button">
            <UploadCloud size={16} />
            Import Evidence
          </button>

          {/* Deliberately disabled until the adequacy engine exists. */}
          <button className="primary-button" type="button" disabled>
            <Play size={16} />
            Run QA Analysis
          </button>
        </div>
      </div>

      <section className="metric-grid four">
        <MetricCard
          icon={<ShieldCheck size={31} />}
          label="RVC"
          value="—"
          detail="Available after adequacy + execution analysis"
          tone="green"
        />

        <MetricCard
          icon={<CheckSquare2 size={31} />}
          label="Adequately Validated"
          value={`— / ${overview.requirements}`}
          detail="Requirements"
          tone="green"
        />

        <MetricCard
          icon={<AlertTriangle size={31} />}
          label="Partial / Inadequate"
          value="— / —"
          detail="Not calculated yet"
          tone="red"
        />

        <MetricCard
          icon={<Waves size={31} />}
          label="Avg. Experimental RVES"
          value="—"
          detail="Available after validation intelligence"
          tone="blue"
        />
      </section>

      <section className="dashboard-grid two-cols">
        <article className="surface-card dashboard-panel">
          <div className="panel-title-row">
            <h2>Current Analysis Foundation</h2>

            <span className="info-chip">Real pipeline outputs</span>
          </div>

          <div className="foundation-grid">
            <FoundationStat
              label="Requirements"
              value={overview.requirements}
            />

            <FoundationStat
              label="Acceptance Criteria"
              value={overview.acceptance_criteria}
            />

            <FoundationStat label="Derived RVUs" value={overview.rvus} />

            <FoundationStat
              label="Expected Evidence Profiles"
              value={overview.expected_profiles}
            />

            <FoundationStat
              label="Normalized Evidence"
              value={overview.evidence_items}
            />

            <FoundationStat
              label="Automated Tests"
              value={overview.automated_tests}
            />
          </div>
        </article>

        <article className="surface-card dashboard-panel">
          <div className="panel-title-row">
            <h2>Priority QA Attention</h2>

            <Link to="/quality/requirements">View All</Link>
          </div>

          <div className="attention-table">
            <div className="attention-row head">
              <span>Requirement ID</span>

              <span>Requirement</span>

              <span>Type</span>

              <span>Status</span>
            </div>

            {highRisk.map((requirement) => (
              <Link
                className="attention-row"
                key={requirement.requirement_id}
                to={`/quality/requirements/` + requirement.requirement_id}
              >
                <span className="attention-id">
                  {requirement.requirement_id}
                </span>

                <span>{requirement.title}</span>

                <span>
                  <StatusPill
                    tone={requirement.type === "FUNCTIONAL" ? "blue" : "purple"}
                  >
                    {requirement.type === "FUNCTIONAL"
                      ? "Functional"
                      : "Non-Functional"}
                  </StatusPill>
                </span>

                <span>
                  <StatusPill tone="neutral">Pending</StatusPill>
                </span>
              </Link>
            ))}
          </div>
        </article>

        <article className="surface-card dashboard-panel">
          <div className="panel-title-row">
            <h2>Top Validation Gaps</h2>
          </div>

          <div className="empty-chart">
            <strong>Gap analysis not available yet</strong>

            <p>
              Missing evidence, weak assertions, boundary gaps and NFR
              mismatches will appear after type-aware adequacy analysis.
            </p>
          </div>
        </article>

        <article className="surface-card dashboard-panel">
          <div className="panel-title-row">
            <h2>Top Validation Details</h2>
          </div>

          <div className="empty-table-state">
            <span>Issue</span>
            <span>Severity</span>
            <span>Requirement ID</span>

            <p>—</p>
            <p>—</p>
            <p>—</p>
          </div>
        </article>
      </section>
    </>
  );
}

function FoundationStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="foundation-stat">
      <strong>{value}</strong>

      <span>{label}</span>
    </div>
  );
}
