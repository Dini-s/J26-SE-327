from __future__ import annotations

from agents.quality_agent.schemas import (
    QAGap,
    Recommendation,
    RVUAdequacySummary,
    RVUValidationResult,
)


class GapService:
    """
    Generate deterministic and grounded
    QA gaps and recommended actions.

    Natural-language generation may later
    improve wording but must never modify
    the underlying validation decision.
    """

    def generate(
        self,
        *,
        validations: list[
            RVUValidationResult
        ],
        summaries: list[
            RVUAdequacySummary
        ],
    ) -> tuple[
        list[QAGap],
        list[Recommendation],
    ]:

        summary_map = {
            item.rvu_id: item
            for item
            in summaries
        }

        gaps: list[QAGap] = []
        recommendations: list[
            Recommendation
        ] = []

        counter = 1

        for validation in validations:
            summary = (
                summary_map[
                    validation.rvu_id
                ]
            )

            reasons = sorted(
                set(
                    validation.reason_codes
                    +
                    summary.reason_codes
                )
            )

            if (
                validation
                .validation_status
                == "NOT_ASSESSED"
            ):
                gap_type = (
                    "SPECIALIZED_REVIEW_REQUIRED"
                )

                severity = "MEDIUM"

                description = (
                    "Automatic adequacy "
                    "assessment is not supported "
                    "for this evidence type."
                )

                recommendation = (
                    "Collect or review the "
                    "specialized QA evidence "
                    "defined for this "
                    "non-functional requirement."
                )

                action = (
                    "REVIEW_SPECIALIZED_EVIDENCE"
                )

            elif not (
                validation
                .evidence_found
            ):
                gap_type = (
                    "MISSING_EVIDENCE"
                )

                severity = "HIGH"

                description = (
                    "No sufficiently relevant "
                    "QA evidence was found "
                    "for this RVU."
                )

                recommendation = (
                    "Create QA evidence that "
                    "directly validates this "
                    "RVU and its expected "
                    "outcome."
                )

                action = "CREATE_TEST"

            elif (
                validation
                .adequacy_status
                == "INADEQUATE"
            ):
                gap_type = (
                    "INADEQUATE_EVIDENCE"
                )

                severity = "HIGH"

                description = (
                    "Relevant evidence exists "
                    "but is technically "
                    "insufficient for the RVU."
                )

                recommendation = (
                    self
                    ._recommendation_from_reasons(
                        reasons
                    )
                )

                action = (
                    "STRENGTHEN_TEST"
                )

            elif (
                validation
                .adequacy_status
                == "PARTIAL"
            ):
                gap_type = (
                    "PARTIAL_EVIDENCE"
                )

                severity = "MEDIUM"

                description = (
                    "Evidence partially covers "
                    "the expected validation "
                    "conditions."
                )

                recommendation = (
                    self
                    ._recommendation_from_reasons(
                        reasons
                    )
                )

                action = (
                    "IMPROVE_TEST"
                )

            elif not (
                validation
                .execution_satisfied
            ):
                gap_type = (
                    "FAILED_OR_UNEXECUTED"
                )

                severity = "HIGH"

                description = (
                    "Technically adequate "
                    "evidence exists, but "
                    "successful execution has "
                    "not been demonstrated."
                )

                recommendation = (
                    "Execute the adequate "
                    "evidence successfully or "
                    "investigate the failed "
                    "execution result."
                )

                action = (
                    "EXECUTE_OR_FIX"
                )

            else:
                continue

            gap_id = (
                f"GAP-{counter:04d}"
            )

            gap = QAGap(
                gap_id=gap_id,

                requirement_id=(
                    validation
                    .requirement_id
                ),

                rvu_id=(
                    validation
                    .rvu_id
                ),

                gap_type=gap_type,
                severity=severity,

                description=description,

                reason_codes=reasons,

                evidence_id=(
                    validation
                    .best_evidence_id
                ),
            )

            gaps.append(gap)

            recommendations.append(
                Recommendation(
                    recommendation_id=(
                        f"REC-{counter:04d}"
                    ),

                    gap_id=gap_id,

                    requirement_id=(
                        validation
                        .requirement_id
                    ),

                    rvu_id=(
                        validation
                        .rvu_id
                    ),

                    action_type=action,

                    recommendation=(
                        recommendation
                    ),

                    grounded_in=[
                        gap_id,
                        *reasons,
                    ],
                )
            )

            counter += 1

        return (
            gaps,
            recommendations,
        )

    @staticmethod
    def _recommendation_from_reasons(
        reasons: list[str],
    ) -> str:

        if (
            "WEAK_ORACLE"
            in reasons
        ):
            return (
                "Add explicit assertions "
                "that prove the expected "
                "RVU outcome."
            )

        if (
            "SCENARIO_MISMATCH"
            in reasons
        ):
            return (
                "Add the required positive, "
                "negative, boundary or state "
                "validation scenario."
            )

        if (
            "PRECONDITION_MISMATCH"
            in reasons
        ):
            return (
                "Update the test setup to "
                "represent the required "
                "preconditions."
            )

        if (
            "INPUT_MISMATCH"
            in reasons
        ):
            return (
                "Add inputs that directly "
                "exercise the required RVU."
            )

        if (
            "CONDITION_MISMATCH"
            in reasons
        ):
            return (
                "Strengthen the test so that "
                "its condition directly proves "
                "the required behaviour."
            )

        if any(
            reason.startswith(
                "NFR_"
            )
            for reason
            in reasons
        ):
            return (
                "Align the performance metric, "
                "percentile, threshold, load, "
                "duration and scope with the "
                "Expected Evidence Profile."
            )

        return (
            "Strengthen the available "
            "evidence to cover the missing "
            "validation conditions."
        )