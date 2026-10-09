import {
  AlertTriangle,
  CheckSquare2,
  ClipboardCheck,
  Download,
  FileSearch,
  ShieldAlert,
  Sparkles,
  Waves,
} from "lucide-react";

import { useEffect, useMemo, useState } from "react";

import { useParams } from "react-router-dom";

import {
  EmptyAnalysis,
  ErrorPanel,
  LoadingPanel,
  MetricCard,
  StatusPill,
} from "../components/UI";

import {
  getEvidence,
  getRequirement,
  retrieveEvidence,
} from "../services/qualityApi";

import type {
  CandidateMatch,
  EvidenceProfile,
  RequirementDetails,
  RVU,
  ValidationEvidence,
} from "../types/quality";

export function RequirementDetailsPage() {
  const { requirementId = "REQ-PET-001" } = useParams();

  const [details, setDetails] = useState<RequirementDetails | null>(null);

  const [evidence, setEvidence] = useState<ValidationEvidence[]>([]);

  const [selectedRvuId, setSelectedRvuId] = useState<string | null>(null);

  const [matches, setMatches] = useState<CandidateMatch[]>([]);

  const [tab, setTab] = useState<"summary" | "revalidation">("summary");

  const [loading, setLoading] = useState(true);

  const [retrieving, setRetrieving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);

        const [detailsData, evidenceData] = await Promise.all([
          getRequirement(requirementId),
          getEvidence(),
        ]);

        setDetails(detailsData);

        setEvidence(evidenceData);

        setSelectedRvuId(detailsData.rvus[0]?.rvu_id ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [requirementId]);

  useEffect(() => {
    async function retrieve() {
      if (!selectedRvuId) {
        setMatches([]);
        return;
      }

      try {
        setRetrieving(true);

        // Semantic retrieval creates candidates only.
        // It must not be interpreted as an adequacy decision.
        setMatches(await retrieveEvidence(selectedRvuId, "semantic", 5));
      } catch {
        setMatches([]);
      } finally {
        setRetrieving(false);
      }
    }

    void retrieve();
  }, [selectedRvuId]);

  const selectedRvu = useMemo(
    () => details?.rvus.find((item) => item.rvu_id === selectedRvuId) ?? null,
    [details, selectedRvuId],
  );

  const selectedProfile = useMemo(
    () =>
      details?.profiles.find((item) => item.rvu_id === selectedRvuId) ?? null,
    [details, selectedRvuId],
  );

  const evidenceMap = useMemo(
    () => new Map(evidence.map((item) => [item.evidence_id, item])),
    [evidence],
  );

  if (loading) {
    return <LoadingPanel message="Loading requirement details…" />;
  }

  if (error || !details) {
    return <ErrorPanel message={error ?? "Requirement unavailable."} />;
  }

  const requirement = details.requirement;

  return (
    <>
      <div className="details-heading">
        <div>
          <div className="details-title-line">
            <h1>Requirement Details ({requirement.requirement_id})</h1>

            <StatusPill
              tone={
                requirement.risk === "HIGH"
                  ? "red"
                  : requirement.risk === "MEDIUM"
                    ? "orange"
                    : "green"
              }
            >
              {requirement.risk} Risk
            </StatusPill>
          </div>

          <p className="requirement-blue-text">{requirement.title}</p>
        </div>

        <button className="primary-button" type="button" disabled>
          <Download size={17} />
          Export Report
        </button>
      </div>

      <div className="details-tabs">
        <button
          className={tab === "summary" ? "active" : ""}
          type="button"
          onClick={() => setTab("summary")}
        >
          Summary & Evidence
        </button>

        <button
          className={tab === "revalidation" ? "active" : ""}
          type="button"
          onClick={() => setTab("revalidation")}
        >
          Revalidation
        </button>
      </div>

      {tab === "summary" ? (
        <SummaryEvidence
          details={details}
          selectedRvu={selectedRvu}
          selectedProfile={selectedProfile}
          selectedRvuId={selectedRvuId}
          setSelectedRvuId={setSelectedRvuId}
          matches={matches}
          evidenceMap={evidenceMap}
          retrieving={retrieving}
        />
      ) : (
        <RevalidationPlaceholder requirementId={requirement.requirement_id} />
      )}
    </>
  );
}

function SummaryEvidence({
  details,
  selectedRvu,
  selectedProfile,
  selectedRvuId,
  setSelectedRvuId,
  matches,
  evidenceMap,
  retrieving,
}: {
  details: RequirementDetails;

  selectedRvu: RVU | null;

  selectedProfile: EvidenceProfile | null;

  selectedRvuId: string | null;

  setSelectedRvuId: (value: string) => void;

  matches: CandidateMatch[];

  evidenceMap: Map<string, ValidationEvidence>;

  retrieving: boolean;
}) {
  const requirement = details.requirement;

  return (
    <>
      <section className="metric-grid five details-metrics">
        <MetricCard
          icon={<FileSearch size={28} />}
          label="RVC"
          value="—"
          detail="Pending adequacy + execution"
          tone="purple"
        />

        <MetricCard
          icon={<Waves size={28} />}
          label="Experimental RVES"
          value="—"
          detail="Not calculated yet"
          tone="blue"
        />

        <MetricCard
          icon={<CheckSquare2 size={28} />}
          label="Adequate RVUs"
          value={`— / ${details.rvus.length}`}
          detail="Adequacy engine not enabled"
          tone="green"
        />

        <MetricCard
          icon={<ClipboardCheck size={28} />}
          label="Status"
          value="Pending"
          detail="No satisfaction label yet"
          tone="orange"
        />

        <MetricCard
          icon={<ShieldAlert size={28} />}
          label="Risk"
          value={requirement.risk}
          tone="red"
        />
      </section>

      <section className="details-layout">
        <aside className="surface-card requirement-summary-card">
          <h2>Requirement Summary</h2>

          <InfoPair label="ID" value={requirement.requirement_id} />

          <InfoPair
            label="Type"
            value={
              requirement.type === "FUNCTIONAL"
                ? "Functional"
                : "Non-Functional"
            }
          />

          <InfoPair label="Subtype" value={requirement.subtype} />

          <InfoPair label="Source" value={requirement.source} />

          <InfoPair label="Version" value={`v${requirement.version}`} />

          <h3>Acceptance Criteria → Derived RVUs</h3>

          <div className="rvu-summary-list">
            {details.rvus.map((rvu) => (
              <button
                key={rvu.rvu_id}
                type="button"
                className={`rvu-summary-item${
                  selectedRvuId === rvu.rvu_id ? " active" : ""
                }`}
                onClick={() => setSelectedRvuId(rvu.rvu_id)}
              >
                <div>
                  <strong>
                    {rvu.rvu_id.replace(requirement.requirement_id, "RVU")}
                  </strong>

                  <span>{rvu.atomic_text}</span>
                </div>

                <StatusPill tone="neutral">Pending</StatusPill>
              </button>
            ))}
          </div>
        </aside>

        <div className="details-main-column">
          <article className="surface-card evidence-card">
            <div className="panel-title-row">
              <div>
                <h2>Evidence Coverage</h2>

                <span className="section-helper">
                  Candidate retrieval only — semantic match is not adequacy.
                </span>
              </div>

              {selectedProfile ? (
                <StatusPill
                  tone={
                    selectedProfile.support_status === "SUPPORTED"
                      ? "green"
                      : selectedProfile.support_status === "REVIEW_REQUIRED"
                        ? "orange"
                        : "red"
                  }
                >
                  {selectedProfile.support_status}
                </StatusPill>
              ) : null}
            </div>

            <div className="rvu-tabs">
              {details.rvus.map((rvu) => (
                <button
                  key={rvu.rvu_id}
                  type="button"
                  className={selectedRvuId === rvu.rvu_id ? "active" : ""}
                  onClick={() => setSelectedRvuId(rvu.rvu_id)}
                >
                  {rvu.rvu_id.replace(
                    details.requirement.requirement_id,
                    "RVU",
                  )}
                </button>
              ))}
            </div>

            {selectedRvu && selectedProfile ? (
              <div className="selected-rvu-strip">
                <strong>{selectedRvu.atomic_text}</strong>

                <span>{formatProfileCondition(selectedProfile)}</span>
              </div>
            ) : null}

            <div className="table-scroll">
              <table className="data-table evidence-table">
                <thead>
                  <tr>
                    <th>Expected Evidence</th>

                    <th>Matched Evidence</th>

                    <th>Source</th>

                    <th>Type</th>

                    <th>Semantic Match</th>

                    <th>Execution</th>

                    <th>Measured Value</th>

                    <th>Threshold / Condition</th>

                    <th>Adequacy</th>
                  </tr>
                </thead>

                <tbody>
                  {retrieving ? (
                    <tr>
                      <td colSpan={9}>Retrieving semantic candidates…</td>
                    </tr>
                  ) : matches.length ? (
                    matches.map((match) => {
                      const item = evidenceMap.get(match.evidence_id);

                      return (
                        <tr key={match.evidence_id}>
                          <td>{selectedProfile?.evidence_type ?? "—"}</td>

                          <td>
                            <strong>{match.evidence_title}</strong>
                          </td>

                          <td>{match.source_tool}</td>

                          <td>{match.evidence_type}</td>

                          <td
                            className={
                              match.similarity_score >= 0.7
                                ? "score-good"
                                : match.similarity_score >= 0.4
                                  ? "score-medium"
                                  : "score-low"
                            }
                          >
                            {Math.round(match.similarity_score * 100)}%
                          </td>

                          <td>
                            {match.execution_status ? (
                              <StatusPill
                                tone={
                                  match.execution_status === "PASS"
                                    ? "green"
                                    : match.execution_status === "FAIL"
                                      ? "red"
                                      : "orange"
                                }
                              >
                                {match.execution_status}
                              </StatusPill>
                            ) : (
                              <StatusPill tone="neutral">Unknown</StatusPill>
                            )}
                          </td>

                          <td>{formatMeasuredValue(item)}</td>

                          <td>{formatProfileCondition(selectedProfile)}</td>

                          {/* Intentionally blank until type-aware adequacy exists. */}
                          <td>
                            <StatusPill tone="neutral">Pending</StatusPill>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={9}>No candidate evidence returned.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </article>

          <section className="details-bottom-grid">
            <article className="surface-card">
              <h2>Test Quality Findings</h2>

              <EmptyAnalysis
                title="No adequacy findings yet"
                description={
                  "Weak assertions, missing scenarios, " +
                  "configuration mismatches and execution " +
                  "gaps will appear after the adequacy engine."
                }
              />
            </article>

            <article className="surface-card">
              <h2>AI Recommendations</h2>

              <EmptyAnalysis
                title="No recommendations yet"
                description={
                  "Recommendations will be generated only " +
                  "from structured QA gaps. No synthetic " +
                  "recommendations are displayed here."
                }
              />
            </article>
          </section>
        </div>
      </section>
    </>
  );
}

function RevalidationPlaceholder({ requirementId }: { requirementId: string }) {
  return (
    <section className="revalidation-page">
      <div className="revalidation-banner neutral">
        <AlertTriangle size={24} />

        <div>
          <strong>Revalidation analysis is not available yet</strong>

          <p>
            Standalone Component 3 currently has no approved change event for{" "}
            {requirementId}.
          </p>
        </div>

        <StatusPill tone="neutral">Not analyzed</StatusPill>
      </div>

      <div className="change-comparison">
        <div className="comparison-box">
          <span>Previous</span>
          <strong>—</strong>
        </div>

        <div className="comparison-arrow">→</div>

        <div className="comparison-box">
          <span>Current</span>
          <strong>—</strong>
        </div>
      </div>

      <section className="metric-grid four revalidation-metrics">
        <MetricCard
          icon={<CheckSquare2 size={27} />}
          label="Reusable"
          value="—"
          tone="green"
        />

        <MetricCard
          icon={<FileSearch size={27} />}
          label="Modification Required"
          value="—"
          tone="orange"
        />

        <MetricCard
          icon={<AlertTriangle size={27} />}
          label="Outdated"
          value="—"
          tone="red"
        />

        <MetricCard
          icon={<Sparkles size={27} />}
          label="New Evidence Required"
          value="—"
          tone="purple"
        />
      </section>

      <article className="surface-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Evidence / Test</th>

              <th>Previous Validation Purpose</th>

              <th>C3 Decision</th>

              <th>Current Validation Purpose</th>

              <th>Reason</th>

              <th>Action</th>
            </tr>
          </thead>

          <tbody>
            <tr>
              <td colSpan={6} className="empty-cell">
                No revalidation results generated.
              </td>
            </tr>
          </tbody>
        </table>
      </article>

      <section className="details-bottom-grid">
        <article className="surface-card">
          <h2>Revalidation Summary</h2>

          <EmptyAnalysis
            title="No change assessment"
            description={
              "This area will be populated by the " +
              "standalone revalidation engine and later " +
              "by affected-change context from Component 4."
            }
          />
        </article>

        <article className="surface-card">
          <h2>Recommended QA Actions</h2>

          <EmptyAnalysis
            title="No targeted QA actions"
            description={
              "Actions remain empty until an actual " +
              "change impact has been classified."
            }
          />
        </article>
      </section>
    </section>
  );
}

function InfoPair({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-pair">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatProfileCondition(profile: EvidenceProfile | null) {
  if (!profile) {
    return "—";
  }

  const parts: string[] = [];

  if (profile.metric) {
    parts.push(profile.metric.replaceAll("_", " "));
  }

  if (profile.percentile) {
    parts.push(profile.percentile);
  }

  if (profile.operator && profile.threshold != null) {
    parts.push(
      `${profile.operator} ` +
        `${profile.threshold}` +
        (profile.unit ? ` ${profile.unit}` : ""),
    );
  }

  if (profile.load != null) {
    parts.push(`${profile.load} concurrent users`);
  }

  if (profile.duration_seconds != null) {
    parts.push(`${profile.duration_seconds}s duration`);
  }

  return parts.length
    ? parts.join(" · ")
    : (profile.expected_outcomes[0] ?? profile.evidence_type);
}

function formatMeasuredValue(item: ValidationEvidence | undefined) {
  if (!item || item.measured_value == null) {
    return "—";
  }

  return `${item.measured_value}` + (item.unit ? ` ${item.unit}` : "");
}
