import { useCallback, useState } from "react";
import {
  ArrowLeft,
  Activity,
  AlertTriangle,
  ClipboardCheck,
  Download,
  FileCheck2,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import { qualityApi } from "../services/qualityApi";

import {
  Badge,
  DataState,
  Empty,
  Metric,
  PageHeader,
  Panel,
} from "../component/quality/QualityUI";

import {
  downloadJson,
  humanize,
  number,
  percent,
  score,
} from "../services/qualityPresentation";

import { useQualityData } from "../services/useQualityData";


/**
 * Builds the user-facing execution state.
 *
 * Important C3 semantics:
 *
 * 1. Evidence adequacy and execution are independent.
 *
 * 2. Synthetic / controlled PASS or FAIL must NOT be treated
 *    as a genuine execution result.
 *
 * 3. Controlled outcomes may still be shown as secondary
 *    information because they are useful for demonstrating
 *    and testing the C3 reasoning pipeline.
 *
 * 4. Only genuine observed execution can confirm validation.
 */
function getExecutionPresentation(evidence) {
  const metadata =
    evidence?.metadata || {};

  const manualExecution =
    metadata?.manual_execution || {};

  const rawStatus = String(
    evidence?.execution_status ||
      "NOT_EXECUTED"
  ).toUpperCase();

  const executionKind = String(
    metadata?.execution_kind ||
      manualExecution?.execution_kind ||
      ""
  ).toUpperCase();

  const executionSource = String(
    metadata?.execution_source ||
      manualExecution?.execution_source ||
      evidence?.source_tool ||
      ""
  ).toUpperCase();

  const evidenceType = String(
    evidence?.evidence_type ||
      ""
  ).toUpperCase();

  const executionRunId =
    evidence?.execution_run_id ||
    metadata?.execution_run_id ||
    metadata?.run_id ||
    manualExecution?.execution_id ||
    null;

  const explicitObserved =
    metadata?.execution_observed === true ||
    metadata?.observed === true ||
    manualExecution?.execution_observed === true ||
    manualExecution?.observed === true;

  const explicitNotObserved =
    metadata?.execution_observed === false ||
    metadata?.observed === false ||
    manualExecution?.execution_observed === false ||
    manualExecution?.observed === false;

  const synthetic =
    evidence?.synthetic === true ||
    metadata?.synthetic === true ||
    manualExecution?.synthetic === true;

  const controlledMarker =
    executionKind.includes("CONTROLLED") ||
    executionKind.includes("SYNTHETIC") ||
    executionKind.includes("FIXTURE") ||
    executionSource.includes("CONTROLLED") ||
    executionSource.includes("SYNTHETIC") ||
    executionSource.includes("FIXTURE");

  const originalStatus = String(
    metadata?.original_execution_status ||
      manualExecution?.original_status ||
      rawStatus
  ).toUpperCase();

  const blocked =
    rawStatus === "BLOCKED" ||
    originalStatus === "BLOCKED" ||
    executionKind === "BLOCKED";

  const controlled =
    synthetic ||
    controlledMarker ||
    explicitNotObserved;

  /*
   * Controlled outcome may be stored explicitly by the backend.
   *
   * For older controlled evidence where the raw status is still
   * PASS/FAIL, preserve that value as the controlled outcome
   * while displaying NOT_EXECUTED as the real execution state.
   */
  let controlledOutcome =
    metadata?.controlled_outcome ||
    metadata?.legacy_controlled_outcome ||
    manualExecution?.controlled_outcome ||
    null;

  if (
    !controlledOutcome &&
    controlled &&
    ["PASS", "FAIL"].includes(rawStatus)
  ) {
    controlledOutcome =
      rawStatus;
  }

  if (
    controlledOutcome
  ) {
    controlledOutcome =
      String(
        controlledOutcome
      ).toUpperCase();
  }

  /*
   * BLOCKED is not a completed execution.
   */
  if (blocked) {
    return {
      badge: "NOT_EXECUTED",
      label: "Not executed",
      observed: false,
      controlled: false,
      controlledOutcome: null,
      detail:
        "Execution was blocked; no qualifying execution confirmed.",
    };
  }

  /*
   * Synthetic / controlled evidence.
   *
   * The controlled PASS/FAIL can be shown underneath as
   * research/demo information, but the primary execution
   * status remains NOT_EXECUTED.
   */
  if (controlled) {
    return {
      badge: "NOT_EXECUTED",
      label: "Not executed",
      observed: false,
      controlled: true,
      controlledOutcome,
      detail:
        "Real execution has not been confirmed.",
    };
  }

  /*
   * Explicit execution provenance.
   */
  const observedKind = [
    "OBSERVED",
    "REAL",
    "TOOL_EXECUTION",
    "MANUAL_OBSERVED",
  ].includes(
    executionKind
  );

  /*
   * Execution reports coming from real automated/performance
   * test tools may be identified by a run ID.
   */
  const reportBackedExecution =
    Boolean(
      executionRunId
    ) &&
    [
      "AUTOMATED_TEST",
      "PERFORMANCE_EVIDENCE",
    ].includes(
      evidenceType
    ) &&
    [
      "PASS",
      "FAIL",
      "SKIPPED",
      "ERROR",
    ].includes(
      rawStatus
    );

  const observed =
    explicitObserved ||
    observedKind ||
    reportBackedExecution;

  /*
   * Genuine PASS.
   */
  if (
    observed &&
    rawStatus === "PASS"
  ) {
    return {
      badge: "PASS",
      label: "Observed PASS",
      observed: true,
      controlled: false,
      controlledOutcome: null,
      detail:
        "Execution confirmed.",
    };
  }

  /*
   * Genuine FAIL.
   */
  if (
    observed &&
    rawStatus === "FAIL"
  ) {
    return {
      badge: "FAIL",
      label: "Observed FAIL",
      observed: true,
      controlled: false,
      controlledOutcome: null,
      detail:
        "Execution confirmed, but the expected result was not satisfied.",
    };
  }

  /*
   * Skipped execution.
   */
  if (
    rawStatus === "SKIPPED"
  ) {
    return {
      badge: "SKIPPED",
      label: "Skipped",
      observed: false,
      controlled: false,
      controlledOutcome: null,
      detail:
        "The test was skipped and does not confirm validation.",
    };
  }

  /*
   * Execution error.
   */
  if (
    rawStatus === "ERROR"
  ) {
    return {
      badge: "ERROR",
      label: "Execution error",
      observed: false,
      controlled: false,
      controlledOutcome: null,
      detail:
        "Execution did not complete successfully.",
    };
  }

  /*
   * Conservative fallback.
   *
   * A PASS or FAIL without qualifying provenance is never
   * presented as confirmed execution.
   */
  return {
    badge: "NOT_EXECUTED",
    label: "Not executed",
    observed: false,
    controlled: false,
    controlledOutcome: null,
    detail:
      "No qualifying observed execution has been confirmed.",
  };
}


/**
 * Execution column presentation.
 *
 * Example controlled evidence:
 *
 * Not executed
 * Real execution has not been confirmed.
 * Controlled outcome: PASS · Synthetic fixture only
 *
 * Example real execution:
 *
 * PASS
 * Execution confirmed.
 */
function ExecutionCell({
  evidence,
}) {
  const execution =
    getExecutionPresentation(
      evidence
    );

  return (
    <div>
      <Badge
        value={
          execution.badge
        }
      />

      <small>
        {execution.detail}
      </small>

      {execution.controlled &&
        execution.controlledOutcome && (
          <small>
            <strong>
              Controlled outcome:{" "}
              {
                execution.controlledOutcome
              }
            </strong>
            {" · "}
            Synthetic fixture only
          </small>
        )}
    </div>
  );
}


export default function RequirementDetailsPage({
  requirementId,
}) {
  const loader =
    useCallback(
      () =>
        qualityApi.getRequirement(
          requirementId
        ),
      [requirementId]
    );

  const {
    data,
    loading,
    error,
    refresh,
  } = useQualityData(
    loader
  );

  const [
    selectedId,
    setSelectedId,
  ] = useState(
    null
  );

  const [
    tab,
    setTab,
  ] = useState(
    "evidence"
  );

  const selected =
    data?.rvus?.find(
      (item) =>
        item.rvu.rvu_id ===
        selectedId
    ) ||
    data?.rvus?.[0];

  const intelligence =
    data?.intelligence;

  const gaps = (
    data?.gaps || []
  ).filter(
    (item) =>
      item.rvu_id ===
      selected?.rvu.rvu_id
  );

  const recommendations = (
    data?.recommendations || []
  ).filter(
    (item) =>
      item.rvu_id ===
      selected?.rvu.rvu_id
  );

  return (
    <div className="qi-page">
      <Link
        className="qi-back"
        to="/quality/requirements"
      >
        <ArrowLeft
          size={15}
        />

        All requirements
      </Link>

      <PageHeader
        eyebrow={`REQUIREMENT / ${requirementId}`}
        title={`Requirement Details (${requirementId})`}
        description={
          data
            ? `${data.requirement.title} — ${data.requirement.text}`
            : (
              "Inspect validation checks, supporting evidence, " +
              "and the impact of requirement changes."
            )
        }
      >
        <button
          className="qi-button primary"
          disabled={
            !data ||
            loading
          }
          onClick={() =>
            downloadJson(
              data,
              `${requirementId}-evidence-review.json`
            )
          }
        >
          <Download
            size={16}
          />

          Export requirement
        </button>
      </PageHeader>

      <DataState
        loading={loading}
        error={error}
        retry={refresh}
      />

      {data &&
        !loading &&
        !error && (
          <>
            <div className="qi-inline">
              <Badge
                value={
                  data
                    .requirement
                    .type
                }
              />

              <Badge
                value={
                  data
                    .requirement
                    .risk
                }
              />

              <span className="qi-muted">
                Risk level
              </span>

              <span className="qi-meta-chip">
                Version{" "}
                {data
                  .requirement
                  .version ??
                  "not supplied"}
              </span>

              <span className="qi-meta-chip">
                {humanize(
                  data
                    .requirement
                    .subtype
                )}
              </span>
            </div>

            <nav
              className="qi-tabs"
              aria-label="Requirement views"
            >
              <button
                className={
                  tab ===
                  "evidence"
                    ? "active"
                    : ""
                }
                aria-pressed={
                  tab ===
                  "evidence"
                }
                onClick={() =>
                  setTab(
                    "evidence"
                  )
                }
              >
                Summary & Evidence
              </button>

              <button
                className={
                  tab ===
                  "changes"
                    ? "active"
                    : ""
                }
                aria-pressed={
                  tab ===
                  "changes"
                }
                onClick={() =>
                  setTab(
                    "changes"
                  )
                }
              >
                Revalidation

                <span>
                  {data
                    .revalidation
                    ?.length ||
                    0}
                </span>
              </button>
            </nav>

            {tab ===
              "evidence" && (
              <div className="qi-metrics five">
                <Metric
                  icon={
                    ShieldCheck
                  }
                  label="Evidence coverage · RVC"
                  value={
                    intelligence
                      ?.total_rvus
                      ? percent(
                          intelligence
                            .rvc_percent
                        )
                      : "—"
                  }
                  detail={`${number(
                    intelligence
                      ?.adequate_rvus
                  )} of ${number(
                    intelligence
                      ?.total_rvus
                  )} checks adequate`}
                  tone="teal"
                />

                <Metric
                  icon={
                    Activity
                  }
                  label="Evidence score · RVES"
                  value={
                    intelligence
                      ?.validation_status ===
                    "NOT_ASSESSED"
                      ? "Not assessed"
                      : score(
                          intelligence
                            ?.rves
                        )
                  }
                  detail="Experimental · scale 0–1"
                  tone="blue"
                />

                <Metric
                  icon={
                    FileCheck2
                  }
                  label="Adequate checks"
                  value={`${number(
                    intelligence
                      ?.adequate_rvus
                  )} / ${number(
                    intelligence
                      ?.total_rvus
                  )}`}
                  detail="Evidence adequacy, separate from execution"
                  tone="teal"
                />

                <Metric
                  icon={
                    ClipboardCheck
                  }
                  label="Validation status"
                  value={
                    <Badge
                      value={
                        intelligence
                          ?.validation_status ||
                        "NOT_ASSESSED"
                      }
                      requirement
                    />
                  }
                  detail={`${number(
                    intelligence
                      ?.validated_rvus
                  )} checks execution-confirmed`}
                  tone="amber"
                />

                <Metric
                  icon={
                    AlertTriangle
                  }
                  label="Requirement risk"
                  value={
                    <Badge
                      value={
                        data
                          .requirement
                          .risk
                      }
                    />
                  }
                  detail="Risk classification of the requirement"
                  tone="rose"
                />
              </div>
            )}

            {tab ===
            "evidence" ? (
              <div
                className="qi-detail-grid"
                id="check-review"
              >
                <Panel title="Requirement Summary">
                  <dl className="qi-requirement-meta">
                    <div>
                      <dt>
                        ID
                      </dt>

                      <dd>
                        {
                          requirementId
                        }
                      </dd>
                    </div>

                    <div>
                      <dt>
                        Type
                      </dt>

                      <dd>
                        {humanize(
                          data
                            .requirement
                            .type
                        )}
                      </dd>
                    </div>

                    <div>
                      <dt>
                        Subtype
                      </dt>

                      <dd>
                        {humanize(
                          data
                            .requirement
                            .subtype
                        )}
                      </dd>
                    </div>

                    <div>
                      <dt>
                        Source
                      </dt>

                      <dd>
                        {data
                          .requirement
                          .source ||
                          "Not supplied"}
                      </dd>
                    </div>

                    <div>
                      <dt>
                        Version
                      </dt>

                      <dd>
                        {data
                          .requirement
                          .version ??
                          "Not supplied"}
                      </dd>
                    </div>

                    <div>
                      <dt>
                        Execution confirmed
                      </dt>

                      <dd>
                        {number(
                          intelligence
                            ?.validated_rvus
                        )}{" "}
                        /{" "}
                        {number(
                          intelligence
                            ?.supported_rvus
                        )}{" "}
                        supported
                      </dd>
                    </div>
                  </dl>

                  <h3 className="qi-subsection-heading">
                    Acceptance criteria
                    {" → "}
                    validation checks
                  </h3>

                  <div className="qi-check-list">
                    {(data.rvus ||
                      []).map(
                      (
                        item,
                        index
                      ) => (
                        <button
                          className={`qi-check-card ${
                            selected
                              ?.rvu
                              .rvu_id ===
                            item.rvu
                              .rvu_id
                              ? "active"
                              : ""
                          }`}
                          key={
                            item
                              .rvu
                              .rvu_id
                          }
                          onClick={() =>
                            setSelectedId(
                              item
                                .rvu
                                .rvu_id
                            )
                          }
                          aria-pressed={
                            selected
                              ?.rvu
                              .rvu_id ===
                            item.rvu
                              .rvu_id
                          }
                        >
                          <span className="qi-check-number">
                            {String(
                              index +
                                1
                            ).padStart(
                              2,
                              "0"
                            )}
                          </span>

                          <div>
                            <strong>
                              {
                                item
                                  .rvu
                                  .atomic_text
                              }
                            </strong>

                            <small>
                              {
                                item
                                  .rvu
                                  .rvu_id
                              }
                            </small>

                            <Badge
                              value={
                                item
                                  .adequacy_summary
                                  ?.adequacy_status ||
                                "NOT_ASSESSED"
                              }
                            />
                          </div>
                        </button>
                      )
                    )}
                  </div>

                  {!data
                    .rvus
                    ?.length && (
                    <Empty title="No checks available">
                      Run analysis to
                      derive validation
                      checks for this
                      requirement.
                    </Empty>
                  )}
                </Panel>

                <div className="qi-stack">
                  <Panel
                    title="Evidence Coverage"
                    description="Choose a validation check to inspect the evidence matched to it."
                  >
                    <div
                      className="qi-rvu-tabs"
                      aria-label="Select validation check"
                    >
                      {(data.rvus ||
                        []).map(
                        (
                          item,
                          index
                        ) => (
                          <button
                            key={
                              item
                                .rvu
                                .rvu_id
                            }
                            className={
                              selected
                                ?.rvu
                                .rvu_id ===
                              item.rvu
                                .rvu_id
                                ? "active"
                                : ""
                            }
                            aria-pressed={
                              selected
                                ?.rvu
                                .rvu_id ===
                              item.rvu
                                .rvu_id
                            }
                            onClick={() =>
                              setSelectedId(
                                item
                                  .rvu
                                  .rvu_id
                              )
                            }
                            title={
                              item
                                .rvu
                                .atomic_text
                            }
                          >
                            RVU{" "}
                            {index +
                              1}
                          </button>
                        )
                      )}
                    </div>

                    <EvidenceReview
                      selected={
                        selected
                      }
                      performance={
                        data
                          .requirement
                          .subtype ===
                        "PERFORMANCE"
                      }
                    />
                  </Panel>

                  <div className="qi-grid two">
                    <Panel
                      title="Test Quality Findings"
                      description="Findings for the selected check."
                    >
                      {gaps.length ? (
                        <div className="qi-findings">
                          {gaps.map(
                            (
                              item
                            ) => (
                              <article
                                className="qi-finding"
                                key={
                                  item
                                    .gap_id
                                }
                              >
                                <Badge
                                  value={
                                    item
                                      .severity
                                  }
                                />

                                <p>
                                  {
                                    item
                                      .description
                                  }
                                </p>
                              </article>
                            )
                          )}
                        </div>
                      ) : (
                        <Empty title="No gaps returned">
                          No gap was
                          generated for
                          the selected
                          check. Review
                          its assessment
                          status above.
                        </Empty>
                      )}
                    </Panel>

                    <Panel
                      title="Recommended QA Actions"
                      description="Actions generated from the selected check’s findings."
                    >
                      {recommendations.length ? (
                        <ol className="qi-action-list">
                          {recommendations.map(
                            (
                              item
                            ) => (
                              <li
                                key={
                                  item
                                    .recommendation_id
                                }
                              >
                                {
                                  item
                                    .recommendation
                                }
                              </li>
                            )
                          )}
                        </ol>
                      ) : (
                        <Empty title="No actions returned">
                          The analysis
                          has not
                          generated a
                          recommendation
                          for this check.
                        </Empty>
                      )}
                    </Panel>
                  </div>
                </div>
              </div>
            ) : (
              <ChangeImpact
                reports={
                  data
                    .revalidation ||
                  []
                }
              />
            )}
          </>
        )}
    </div>
  );
}


function ChangeImpact({
  reports,
}) {
  const [
    selectedId,
    setSelectedId,
  ] = useState(
    null
  );

  const selected =
    reports.find(
      (item) =>
        item.change_id ===
        selectedId
    ) ||
    reports[0];

  if (!selected) {
    return (
      <Panel title="Change impact">
        <Empty title="No requirement changes to review">
          No change case
          currently targets
          this requirement.
          Revalidation
          decisions appear
          here when a change
          case is available.
        </Empty>
      </Panel>
    );
  }

  return (
    <div className="qi-stack">
      {reports.length >
        1 && (
        <label className="qi-select-label">
          Change case

          <select
            value={
              selected
                .change_id
            }
            onChange={(
              event
            ) =>
              setSelectedId(
                event
                  .target
                  .value
              )
            }
          >
            {reports.map(
              (item) => (
                <option
                  key={
                    item
                      .change_id
                  }
                >
                  {
                    item
                      .change_id
                  }
                </option>
              )
            )}
          </select>
        </label>
      )}

      <div className="qi-grid two">
        <Panel title="Previous requirement">
          <p className="qi-body-text">
            {
              selected
                .previous_text
            }
          </p>
        </Panel>

        <Panel title="Updated requirement">
          <p className="qi-body-text">
            {
              selected
                .current_text
            }
          </p>
        </Panel>
      </div>

      <dl className="qi-change-meta">
        <div>
          <dt>
            Change ID
          </dt>

          <dd>
            {
              selected
                .change_id
            }
          </dd>
        </div>

        <div>
          <dt>
            Change type
          </dt>

          <dd>
            {humanize(
              selected
                .change_type
            )}
          </dd>
        </div>

        <div>
          <dt>
            Checks affected
          </dt>

          <dd>
            {selected
              .affected_rvu_ids
              ?.length ||
              0}
          </dd>
        </div>

        <div>
          <dt>
            Affected checks
          </dt>

          <dd>
            {selected
              .affected_rvu_ids
              ?.join(
                ", "
              ) ||
              "Not supplied"}
          </dd>
        </div>
      </dl>

      <div className="qi-metrics">
        <Metric
          label="Evidence reusable"
          value={number(
            selected
              .reusable_count
          )}
          detail="Can continue to support the changed requirement."
          tone="teal"
        />

        <Metric
          label="Evidence needs updates"
          value={number(
            selected
              .modification_required_count
          )}
          detail="Requires modification before reuse."
          tone="amber"
        />

        <Metric
          label="Evidence outdated"
          value={number(
            selected
              .outdated_count
          )}
          detail="No longer supports the updated validation purpose."
        />

        <Metric
          label="New evidence needed"
          value={number(
            selected
              .new_evidence_required_count
          )}
          detail="Additional evidence must be created or linked."
          tone="blue"
        />
      </div>

      <Panel
        title="Evidence reuse decisions"
        description="Review why each asset can be reused, changed, or replaced."
      >
        <div className="qi-table-scroll">
          <table className="qi-table">
            <thead>
              <tr>
                <th>
                  Evidence / test
                </th>

                <th>
                  Previous validation purpose
                </th>

                <th>
                  Decision
                </th>

                <th>
                  Current validation purpose
                </th>

                <th>
                  Reason
                </th>

                <th>
                  Next action
                </th>
              </tr>
            </thead>

            <tbody>
              {(selected
                .decisions ||
                []).map(
                (
                  item,
                  index
                ) => (
                  <tr
                    key={
                      index
                    }
                  >
                    <td>
                      <strong>
                        {
                          item
                            .evidence_name
                        }
                      </strong>
                    </td>

                    <td>
                      {item
                        .previous_validation_purpose ||
                        "Not applicable"}
                    </td>

                    <td>
                      <Badge
                        value={
                          item
                            .classification
                        }
                      />
                    </td>

                    <td>
                      {item
                        .current_validation_purpose ||
                        "Not supplied"}
                    </td>

                    <td>
                      {item
                        .reason ||
                        item
                          .reasoning ||
                        "No reason supplied"}
                    </td>

                    <td>
                      {item
                        .action ||
                        item
                          .recommended_action ||
                        "No action supplied"}
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="qi-grid two">
        <Panel title="Revalidation Summary">
          <ul className="qi-clean-list">
            <li>
              {number(
                selected
                  .reusable_count
              )}{" "}
              evidence assets
              remain reusable.
            </li>

            <li>
              {number(
                selected
                  .modification_required_count
              )}{" "}
              require
              modification.
            </li>

            <li>
              {number(
                selected
                  .outdated_count
              )}{" "}
              are outdated
              for the updated
              requirement.
            </li>

            <li>
              {number(
                selected
                  .new_evidence_required_count
              )}{" "}
              new evidence
              items are
              needed.
            </li>
          </ul>
        </Panel>

        <Panel title="Recommended QA Actions">
          {selected
            .recommended_actions
            ?.length ? (
            <ol className="qi-action-list">
              {selected
                .recommended_actions
                .map(
                  (
                    action,
                    index
                  ) => (
                    <li
                      key={
                        index
                      }
                    >
                      {
                        action
                      }
                    </li>
                  )
                )}
            </ol>
          ) : (
            <Empty title="No additional actions supplied">
              Review the next
              action for each
              evidence decision
              above.
            </Empty>
          )}
        </Panel>
      </div>
    </div>
  );
}


function EvidenceReview({
  selected,
  performance,
}) {
  if (!selected) {
    return (
      <Empty title="No validation check selected">
        Choose a check
        from the
        requirement
        summary.
      </Empty>
    );
  }

  const profile =
    selected.profile;

  const expected =
    profile
      ?.expected_outcomes
      ?.join("; ") ||
    profile
      ?.required_assertions
      ?.join("; ") ||
    selected
      .rvu
      .atomic_text;

  const threshold =
    profile
      ?.threshold ==
    null
      ? "Not supplied"
      : `${profile.metric || ""} ${
          profile.percentile || ""
        } ${
          profile.operator || ""
        } ${
          profile.threshold
        } ${
          profile.unit || ""
        }`;

  const executionConfirmed =
    selected
      .validation
      ?.execution_satisfied ===
    true;

  return (
    <>
      <div className="qi-selected-check">
        <strong>
          {
            selected
              .rvu
              .rvu_id
          }
        </strong>

        <span>
          {
            selected
              .rvu
              .atomic_text
          }
        </span>

        <Badge
          value={
            selected
              .adequacy_summary
              ?.adequacy_status ||
            "NOT_ASSESSED"
          }
        />
      </div>

      <p className="qi-table-help">
        Match relevance
        measures
        similarity.
        Evidence adequacy
        and qualifying
        execution are
        assessed
        independently.{" "}

        {executionConfirmed
          ? (
            "A qualifying observed execution is confirmed for this check."
          )
          : (
            "Adequate evidence may exist, but no qualifying observed execution is confirmed for this check."
          )}
      </p>

      {profile
        ?.support_reason && (
        <div className="qi-note">
          {
            profile
              .support_reason
          }
        </div>
      )}

      {selected
        .evidence_assessments
        ?.length ? (
        <div className="qi-table-scroll">
          <table className="qi-table qi-evidence-table">
            <thead>
              <tr>
                <th>
                  Expected evidence
                </th>

                <th>
                  Matched evidence
                </th>

                <th>
                  Source / type
                </th>

                <th>
                  Match relevance
                </th>

                <th>
                  Execution
                </th>

                {performance ? (
                  <>
                    <th>
                      Measured value
                    </th>

                    <th>
                      Threshold / condition
                    </th>
                  </>
                ) : (
                  <th>
                    Assertion strength
                  </th>
                )}

                <th>
                  Evidence adequacy
                </th>
              </tr>
            </thead>

            <tbody>
              {selected
                .evidence_assessments
                .map(
                  (item) => {
                    const evidence =
                      item.evidence;

                    return (
                      <tr
                        key={
                          item
                            .assessment_id ||
                          item
                            .evidence_id
                        }
                      >
                        <td>
                          {
                            expected
                          }
                        </td>

                        <td>
                          <strong>
                            {evidence
                              ?.title ||
                              item
                                .evidence_id}
                          </strong>
                        </td>

                        <td>
                          {evidence
                            ?.source_tool
                            ? humanize(
                                evidence
                                  .source_tool
                                  .replace(
                                    /^C3_/,
                                    ""
                                  )
                              )
                            : "Not supplied"}

                          <small>
                            {humanize(
                              evidence
                                ?.evidence_type
                            )}
                          </small>
                        </td>

                        <td>
                          <span
                            className={
                              item
                                .relevance_score >=
                              0.7
                                ? "qi-score-good"
                                : "qi-score-warn"
                            }
                          >
                            {item
                              .relevance_score ==
                            null
                              ? "—"
                              : percent(
                                  item
                                    .relevance_score *
                                    100
                                )}
                          </span>
                        </td>

                        <td>
                          <ExecutionCell
                            evidence={
                              evidence
                            }
                          />
                        </td>

                        {performance ? (
                          <>
                            <td>
                              {evidence
                                ?.measured_value ==
                              null
                                ? "Not supplied"
                                : `${evidence.measured_value} ${
                                    evidence.unit ||
                                    ""
                                  }`}

                              {evidence
                                ?.duration_seconds !=
                                null && (
                                <small>
                                  Duration:{" "}
                                  {
                                    evidence
                                      .duration_seconds
                                  }
                                  s
                                </small>
                              )}

                              {evidence
                                ?.load !=
                                null && (
                                <small>
                                  Load:{" "}
                                  {
                                    evidence
                                      .load
                                  }
                                </small>
                              )}
                            </td>

                            <td>
                              {
                                threshold
                              }

                              {profile
                                ?.load !=
                                null && (
                                <small>
                                  Required
                                  load:{" "}
                                  {
                                    profile
                                      .load
                                  }
                                </small>
                              )}

                              {profile
                                ?.duration_seconds !=
                                null && (
                                <small>
                                  Required
                                  duration:{" "}
                                  {
                                    profile
                                      .duration_seconds
                                  }
                                  s
                                </small>
                              )}
                            </td>
                          </>
                        ) : (
                          <td>
                            <Badge
                              value={
                                item
                                  .assertion_strength ||
                                "NOT_ASSESSED"
                              }
                            />
                          </td>
                        )}

                        <td>
                          <Badge
                            value={
                              item
                                .adequacy_status
                            }
                          />
                        </td>
                      </tr>
                    );
                  }
                )}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title="No assessed evidence">
          Add or link
          suitable
          evidence, then
          rerun quality
          analysis.
        </Empty>
      )}
    </>
  );
}