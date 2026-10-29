from __future__ import annotations

from collections import defaultdict

from agents.quality_agent.schemas import (
    ExpectedEvidenceProfile,
    RequirementIntelligence,
    RequirementRecord,
    RequirementValidationUnit,
    RVUAdequacySummary,
    RVUValidationResult,
    ValidationEvidence,
)

from agents.quality_agent.services.execution_provenance import (
    ExecutionProvenanceService,
)


class ValidationService:
    """
    Requirement-centric validation service.

    Core research rules:

        relevance != adequacy
        adequacy != execution
        synthetic PASS != observed PASS

    An RVU is validated only when:

        evidence is ADEQUATE
        +
        execution is OBSERVED
        +
        execution result satisfies the requirement
    """

    def evaluate_rvus(
        self,
        *,
        rvus: list[
            RequirementValidationUnit
        ],
        profiles: list[
            ExpectedEvidenceProfile
        ],
        summaries: list[
            RVUAdequacySummary
        ],
        evidence: list[
            ValidationEvidence
        ],
    ) -> list[
        RVUValidationResult
    ]:
        profile_map = {
            item.rvu_id:
                item

            for item
            in profiles
        }

        summary_map = {
            item.rvu_id:
                item

            for item
            in summaries
        }

        evidence_map = {
            item.evidence_id:
                item

            for item
            in evidence
        }

        results: list[
            RVUValidationResult
        ] = []

        for rvu in rvus:
            profile = (
                profile_map[
                    rvu.rvu_id
                ]
            )

            summary = (
                summary_map[
                    rvu.rvu_id
                ]
            )

            if (
                summary.adequacy_status
                in {
                    "UNSUPPORTED",
                    "NOT_ASSESSED",
                }
            ):
                results.append(
                    RVUValidationResult(
                        rvu_id=(
                            rvu.rvu_id
                        ),

                        requirement_id=(
                            rvu.requirement_id
                        ),

                        evidence_found=(
                            summary.evidence_found
                        ),

                        adequacy_status=(
                            summary.adequacy_status
                        ),

                        execution_satisfied=(
                            False
                        ),

                        validation_status=(
                            "NOT_ASSESSED"
                        ),

                        best_evidence_id=(
                            summary.best_evidence_id
                        ),

                        reason_codes=(
                            summary.reason_codes
                        ),
                    )
                )

                continue

            successful_id: (
                str | None
            ) = None

            # Execution is checked only against evidence that
            # C3 already considers technically adequate.
            if (
                summary.adequacy_status
                == "ADEQUATE"
            ):
                for evidence_id in (
                    summary.adequate_evidence_ids
                ):
                    item = (
                        evidence_map.get(
                            evidence_id
                        )
                    )

                    if item is None:
                        continue

                    if (
                        self._execution_satisfied(
                            profile,
                            item,
                        )
                    ):
                        successful_id = (
                            evidence_id
                        )

                        break

            execution_satisfied = (
                successful_id
                is not None
            )

            reasons = list(
                summary.reason_codes
            )

            if (
                summary.adequacy_status
                == "ADEQUATE"
                and execution_satisfied
            ):
                validation_status = (
                    "VALIDATED"
                )

            elif (
                summary.adequacy_status
                in {
                    "ADEQUATE",
                    "PARTIAL",
                }
            ):
                validation_status = (
                    "PARTIAL"
                )

                if not (
                    execution_satisfied
                ):
                    reasons.append(
                        (
                            "EXECUTION_"
                            "NOT_CONFIRMED"
                        )
                    )

            else:
                validation_status = (
                    "UNSATISFIED"
                )

            results.append(
                RVUValidationResult(
                    rvu_id=(
                        rvu.rvu_id
                    ),

                    requirement_id=(
                        rvu.requirement_id
                    ),

                    evidence_found=(
                        summary.evidence_found
                    ),

                    adequacy_status=(
                        summary.adequacy_status
                    ),

                    execution_satisfied=(
                        execution_satisfied
                    ),

                    validation_status=(
                        validation_status
                    ),

                    best_evidence_id=(
                        successful_id
                        or summary.best_evidence_id
                    ),

                    reason_codes=sorted(
                        set(
                            reasons
                        )
                    ),
                )
            )

        return results

    def aggregate_requirements(
        self,
        *,
        requirements: list[
            RequirementRecord
        ],
        rvus: list[
            RequirementValidationUnit
        ],
        summaries: list[
            RVUAdequacySummary
        ],
        validations: list[
            RVUValidationResult
        ],
    ) -> list[
        RequirementIntelligence
    ]:
        rvus_by_requirement = (
            defaultdict(
                list
            )
        )

        for rvu in rvus:
            rvus_by_requirement[
                rvu.requirement_id
            ].append(
                rvu
            )

        summary_map = {
            item.rvu_id:
                item

            for item
            in summaries
        }

        validation_map = {
            item.rvu_id:
                item

            for item
            in validations
        }

        output: list[
            RequirementIntelligence
        ] = []

        for requirement in (
            requirements
        ):
            requirement_rvus = (
                rvus_by_requirement[
                    requirement.requirement_id
                ]
            )

            total = len(
                requirement_rvus
            )

            if total == 0:
                output.append(
                    RequirementIntelligence(
                        requirement_id=(
                            requirement.requirement_id
                        ),

                        total_rvus=0,
                        supported_rvus=0,
                        not_assessed_rvus=0,
                        evidence_found_rvus=0,
                        adequate_rvus=0,
                        validated_rvus=0,

                        evidence_found_percent=0.0,

                        adequacy_coverage_percent=0.0,

                        rvc_percent=0.0,

                        assessable_adequacy_percent=0.0,

                        execution_confirmed_percent=0.0,

                        validation_status=(
                            "NOT_ASSESSED"
                        ),

                        rves=0.0,

                        rves_factors={
                            "R_relevance":
                                0.0,

                            "A_adequacy":
                                0.0,

                            "C_completeness":
                                0.0,

                            "E_execution":
                                0.0,
                        },

                        rves_experimental=True,
                    )
                )

                continue

            supported = [
                rvu

                for rvu
                in requirement_rvus

                if (
                    summary_map[
                        rvu.rvu_id
                    ].adequacy_status
                    not in {
                        "UNSUPPORTED",
                        "NOT_ASSESSED",
                    }
                )
            ]

            supported_count = len(
                supported
            )

            not_assessed_count = (
                total
                - supported_count
            )

            evidence_found = sum(
                1

                for rvu
                in supported

                if (
                    validation_map[
                        rvu.rvu_id
                    ].evidence_found
                )
            )

            # RVC = adequate evidence coverage.
            adequate = sum(
                1

                for rvu
                in requirement_rvus

                if (
                    summary_map[
                        rvu.rvu_id
                    ].adequacy_status
                    == "ADEQUATE"
                )
            )

            # Validation requires confirmed execution.
            validated = sum(
                1

                for rvu
                in supported

                if (
                    validation_map[
                        rvu.rvu_id
                    ].validation_status
                    == "VALIDATED"
                )
            )

            evidence_ratio = (
                evidence_found
                / supported_count

                if supported_count
                else 0.0
            )

            rvc_ratio = (
                adequate
                / total

                if total
                else 0.0
            )

            assessable_adequacy_ratio = (
                adequate
                / supported_count

                if supported_count
                else 0.0
            )

            execution_confirmed_ratio = (
                validated
                / supported_count

                if supported_count
                else 0.0
            )

            if supported_count:
                relevance_factor = (
                    sum(
                        summary_map[
                            rvu.rvu_id
                        ].best_relevance_score

                        for rvu
                        in supported
                    )
                    / supported_count
                )

                adequacy_factor = (
                    sum(
                        summary_map[
                            rvu.rvu_id
                        ].best_adequacy_score

                        for rvu
                        in supported
                    )
                    / supported_count
                )

            else:
                relevance_factor = 0.0
                adequacy_factor = 0.0

            completeness_factor = (
                rvc_ratio
            )

            execution_factor = (
                execution_confirmed_ratio
            )

            # Experimental RVES baseline.
            rves = (
                0.25
                * relevance_factor

                + 0.25
                * adequacy_factor

                + 0.25
                * completeness_factor

                + 0.25
                * execution_factor
            )

            if supported_count == 0:
                requirement_status = (
                    "NOT_ASSESSED"
                )

            elif (
                not_assessed_count == 0
                and validated == total
            ):
                requirement_status = (
                    "ADEQUATE"
                )

            elif (
                validated > 0
                or adequate > 0
                or evidence_found > 0
            ):
                requirement_status = (
                    "PARTIAL"
                )

            else:
                requirement_status = (
                    "INADEQUATE"
                )

            output.append(
                RequirementIntelligence(
                    requirement_id=(
                        requirement.requirement_id
                    ),

                    total_rvus=(
                        total
                    ),

                    supported_rvus=(
                        supported_count
                    ),

                    not_assessed_rvus=(
                        not_assessed_count
                    ),

                    evidence_found_rvus=(
                        evidence_found
                    ),

                    adequate_rvus=(
                        adequate
                    ),

                    validated_rvus=(
                        validated
                    ),

                    evidence_found_percent=round(
                        evidence_ratio
                        * 100,
                        2,
                    ),

                    adequacy_coverage_percent=round(
                        rvc_ratio
                        * 100,
                        2,
                    ),

                    rvc_percent=round(
                        rvc_ratio
                        * 100,
                        2,
                    ),

                    assessable_adequacy_percent=round(
                        assessable_adequacy_ratio
                        * 100,
                        2,
                    ),

                    execution_confirmed_percent=round(
                        execution_confirmed_ratio
                        * 100,
                        2,
                    ),

                    validation_status=(
                        requirement_status
                    ),

                    rves=round(
                        rves,
                        4,
                    ),

                    rves_factors={
                        "R_relevance":
                            round(
                                relevance_factor,
                                4,
                            ),

                        "A_adequacy":
                            round(
                                adequacy_factor,
                                4,
                            ),

                        "C_completeness":
                            round(
                                completeness_factor,
                                4,
                            ),

                        "E_execution":
                            round(
                                execution_factor,
                                4,
                            ),
                    },

                    rves_experimental=True,
                )
            )

        return output

    def _execution_satisfied(
        self,
        profile:
        ExpectedEvidenceProfile,

        evidence:
        ValidationEvidence,
    ) -> bool:
        # Synthetic or controlled results can never
        # execution-confirm validation.
        if not (
            ExecutionProvenanceService
            .is_observed(
                evidence
            )
        ):
            return False

        if (
            profile.requirement_type
            == "NON_FUNCTIONAL"
            and (
                profile.requirement_subtype
                == "PERFORMANCE"
            )
        ):
            return (
                self._performance_satisfied(
                    profile,
                    evidence,
                )
            )

        return (
            str(
                evidence.execution_status
                or ""
            ).upper()
            == "PASS"
        )

    def _performance_satisfied(
        self,
        profile:
        ExpectedEvidenceProfile,

        evidence:
        ValidationEvidence,
    ) -> bool:
        if not (
            ExecutionProvenanceService
            .is_observed(
                evidence
            )
        ):
            return False

        if (
            str(
                evidence.execution_status
                or ""
            ).upper()
            != "PASS"
        ):
            return False

        if (
            evidence.measured_value
            is None
            or profile.threshold
            is None
        ):
            return False

        actual = self._normalize(
            evidence.measured_value,
            evidence.unit,
        )

        threshold = self._normalize(
            profile.threshold,
            profile.unit,
        )

        operator = str(
            profile.operator
            or ""
        ).strip()

        if operator == "<":
            return (
                actual
                < threshold
            )

        if operator == "<=":
            return (
                actual
                <= threshold
            )

        if operator == ">":
            return (
                actual
                > threshold
            )

        if operator == ">=":
            return (
                actual
                >= threshold
            )

        if operator in {
            "=",
            "==",
        }:
            return (
                actual
                == threshold
            )

        return False

    @staticmethod
    def _normalize(
        value: float,
        unit: str | None,
    ) -> float:
        value = float(
            value
        )

        if not unit:
            return value

        lower = (
            unit
            .lower()
            .strip()
        )

        if lower in {
            "ms",
            "millisecond",
            "milliseconds",
        }:
            return value

        if lower in {
            "s",
            "sec",
            "second",
            "seconds",
        }:
            return (
                value
                * 1000.0
            )

        if lower in {
            "minute",
            "minutes",
            "min",
        }:
            return (
                value
                * 60_000.0
            )

        if lower in {
            "hour",
            "hours",
            "hr",
        }:
            return (
                value
                * 3_600_000.0
            )

        return value