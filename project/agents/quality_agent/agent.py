from __future__ import annotations

from collections import Counter

from datetime import (
    datetime,
    timezone,
)

from pydantic import TypeAdapter

from agents.quality_agent import config

from agents.quality_agent.schemas import (
    EvidenceAdequacyAssessment,
    ExpectedEvidenceProfile,
    OverviewStats,
    RequirementValidationUnit,
    RevalidationChangeCase,
    RVUAdequacySummary,
    ValidationEvidence,
)

from agents.quality_agent.services.adequacy import (
    AdequacyEngine,
)

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)

from agents.quality_agent.services.evidence_profile import (
    EvidenceProfileGenerator,
)

from agents.quality_agent.services.gap_service import (
    GapService,
)

from agents.quality_agent.services.manual_execution import (
    ManualExecutionService,
)

from agents.quality_agent.services.normalizer import (
    EvidenceNormalizer,
)

from agents.quality_agent.services.retrieval import (
    EvidenceRetrievalService,
)

from agents.quality_agent.services.revalidation import (
    RevalidationService,
)

from agents.quality_agent.services.rvu_extractor import (
    RVUExtractor,
)

from agents.quality_agent.services.validation_service import (
    ValidationService,
)


class QualityAgent:
    def __init__(
        self,
    ):
        config.ensure_directories()

        self.dataset_service = (
            DatasetService()
        )

        self.rvu_extractor = (
            RVUExtractor()
        )

        self.profile_generator = (
            EvidenceProfileGenerator()
        )

        self.normalizer = (
            EvidenceNormalizer()
        )

        self.manual_execution_service = (
            ManualExecutionService()
        )

        self.retrieval_service = (
            EvidenceRetrievalService(
                config.EMBEDDING_MODEL
            )
        )

        self.adequacy_engine = (
            AdequacyEngine()
        )

        self.validation_service = (
            ValidationService()
        )

        self.gap_service = (
            GapService()
        )

        self.revalidation_service = (
            RevalidationService()
        )

    def process_requirements(
        self,
    ):
        requirements = (
            self.dataset_service
            .load_requirements(
                config
                .REQUIREMENTS_PATH
            )
        )

        rvus = (
            self.rvu_extractor
            .extract(
                requirements
            )
        )

        profiles = (
            self.profile_generator
            .generate(
                requirements,
                rvus,
            )
        )

        self.dataset_service.save_json(
            config.RVUS_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in rvus
            ],
        )

        self.dataset_service.save_json(
            config
            .EVIDENCE_PROFILES_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in profiles
            ],
        )

        return {
            "requirements":
                requirements,

            "rvus":
                rvus,

            "profiles":
                profiles,
        }

    def normalize_evidence(
        self,
    ) -> list[
        ValidationEvidence
    ]:
        """
        Normalize automated, manual and
        performance evidence and then overlay
        manual execution records.

        Manual test definitions remain separate
        from manual execution records.
        """

        evidence = (
            self.normalizer
            .normalize(
                manual_path=(
                    config
                    .MANUAL_TESTS_PATH
                ),

                junit_root=(
                    config.JUNIT_ROOT
                ),

                surefire_root=(
                    config.SUREFIRE_ROOT
                ),

                performance_path=(
                    config
                    .PERFORMANCE_PATH
                ),
            )
        )

        evidence = (
            self.manual_execution_service
            .apply(
                evidence=evidence,

                path=(
                    config
                    .MANUAL_EXECUTIONS_PATH
                ),
            )
        )

        self.dataset_service.save_json(
            config
            .NORMALIZED_EVIDENCE_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in evidence
            ],
        )

        return evidence

    def retrieve(
        self,
        rvu_id: str,
        method: str,
        top_k: int | None = None,
    ):
        if not (
            config
            .RVUS_PATH
            .exists()
        ):
            self.process_requirements()

        if not (
            config
            .NORMALIZED_EVIDENCE_PATH
            .exists()
        ):
            self.normalize_evidence()

        rvus = TypeAdapter(
            list[
                RequirementValidationUnit
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config.RVUS_PATH
            )
        )

        target_rvu = next(
            (
                item

                for item
                in rvus

                if (
                    item.rvu_id
                    == rvu_id
                )
            ),
            None,
        )

        if target_rvu is None:
            raise ValueError(
                (
                    "RVU not found: "
                    f"{rvu_id}"
                )
            )

        evidence = TypeAdapter(
            list[
                ValidationEvidence
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config
                .NORMALIZED_EVIDENCE_PATH
            )
        )

        matches = (
            self.retrieval_service
            .retrieve(
                target_rvu,
                evidence,
                method,
                (
                    top_k
                    or config.TOP_K
                ),
            )
        )

        output_path = (
            config.RETRIEVAL_ROOT
            / (
                f"{rvu_id}_"
                f"{method.lower()}.json"
            )
        )

        self.dataset_service.save_json(
            output_path,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in matches
            ],
        )

        return matches

    def overview(
        self,
    ) -> OverviewStats:

        requirements = (
            self.dataset_service
            .load_requirements(
                config
                .REQUIREMENTS_PATH
            )
        )

        acceptance_criteria = sum(
            len(
                item
                .acceptance_criteria
            )

            for item
            in requirements
        )

        rvus = (
            self._load_if_exists(
                config.RVUS_PATH
            )
        )

        profiles = (
            self._load_if_exists(
                config
                .EVIDENCE_PROFILES_PATH
            )
        )

        evidence = (
            self._load_if_exists(
                config
                .NORMALIZED_EVIDENCE_PATH
            )
        )

        return OverviewStats(
            requirements=(
                len(
                    requirements
                )
            ),

            acceptance_criteria=(
                acceptance_criteria
            ),

            functional_requirements=sum(
                1

                for item
                in requirements

                if (
                    item.type
                    == "FUNCTIONAL"
                )
            ),

            non_functional_requirements=sum(
                1

                for item
                in requirements

                if (
                    item.type
                    == "NON_FUNCTIONAL"
                )
            ),

            rvus=len(
                rvus
            ),

            expected_profiles=len(
                profiles
            ),

            evidence_items=len(
                evidence
            ),

            automated_tests=sum(
                1

                for item
                in evidence

                if (
                    item.get(
                        "evidence_type"
                    )
                    == "AUTOMATED_TEST"
                )
            ),

            manual_tests=sum(
                1

                for item
                in evidence

                if (
                    item.get(
                        "evidence_type"
                    )
                    == "MANUAL_TEST"
                )
            ),

            performance_evidence=sum(
                1

                for item
                in evidence

                if (
                    item.get(
                        "evidence_type"
                    )
                    == "PERFORMANCE_EVIDENCE"
                )
            ),
        )

    def analyze_quality(
        self,
        top_k: int = 5,
    ):
        if not (
            config
            .RVUS_PATH
            .exists()
        ):
            self.process_requirements()

        if not (
            config
            .NORMALIZED_EVIDENCE_PATH
            .exists()
        ):
            self.normalize_evidence()

        requirements = (
            self.dataset_service
            .load_requirements(
                config
                .REQUIREMENTS_PATH
            )
        )

        rvus = TypeAdapter(
            list[
                RequirementValidationUnit
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config.RVUS_PATH
            )
        )

        profiles = TypeAdapter(
            list[
                ExpectedEvidenceProfile
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config
                .EVIDENCE_PROFILES_PATH
            )
        )

        evidence = TypeAdapter(
            list[
                ValidationEvidence
            ]
        ).validate_python(
            self.dataset_service
            .load_json(
                config
                .NORMALIZED_EVIDENCE_PATH
            )
        )

        profile_map = {
            item.rvu_id:
                item

            for item
            in profiles
        }

        evidence_map = {
            item.evidence_id:
                item

            for item
            in evidence
        }

        assessments: list[
            EvidenceAdequacyAssessment
        ] = []

        summaries: list[
            RVUAdequacySummary
        ] = []

        for rvu in rvus:
            profile = (
                profile_map[
                    rvu.rvu_id
                ]
            )

            current_assessments: list[
                EvidenceAdequacyAssessment
            ] = []

            if (
                profile.support_status
                == "SUPPORTED"
            ):
                matches = (
                    self.retrieve(
                        rvu_id=(
                            rvu.rvu_id
                        ),

                        method=(
                            "semantic"
                        ),

                        top_k=(
                            top_k
                        ),
                    )
                )

                for match in matches:
                    evidence_item = (
                        evidence_map.get(
                            match.evidence_id
                        )
                    )

                    if (
                        evidence_item
                        is None
                    ):
                        continue

                    result = (
                        self
                        .adequacy_engine
                        .assess(
                            profile=profile,

                            rvu=rvu,

                            match=match,

                            evidence=(
                                evidence_item
                            ),
                        )
                    )

                    current_assessments.append(
                        result
                    )

                    assessments.append(
                        result
                    )

            summary = (
                self
                .adequacy_engine
                .summarize(
                    rvu=rvu,

                    profile=profile,

                    assessments=(
                        current_assessments
                    ),
                )
            )

            summaries.append(
                summary
            )

        validations = (
            self.validation_service
            .evaluate_rvus(
                rvus=rvus,

                profiles=profiles,

                summaries=summaries,

                evidence=evidence,
            )
        )

        intelligence = (
            self.validation_service
            .aggregate_requirements(
                requirements=(
                    requirements
                ),

                rvus=rvus,

                summaries=summaries,

                validations=(
                    validations
                ),
            )
        )

        (
            gaps,
            recommendations,
        ) = (
            self.gap_service
            .generate(
                validations=(
                    validations
                ),

                summaries=(
                    summaries
                ),
            )
        )

        self.dataset_service.save_json(
            config
            .ADEQUACY_ASSESSMENTS_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in assessments
            ],
        )

        self.dataset_service.save_json(
            config
            .RVU_ADEQUACY_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in summaries
            ],
        )

        self.dataset_service.save_json(
            config
            .RVU_VALIDATION_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in validations
            ],
        )

        self.dataset_service.save_json(
            config
            .REQUIREMENT_INTELLIGENCE_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in intelligence
            ],
        )

        self.dataset_service.save_json(
            config.GAPS_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in gaps
            ],
        )

        self.dataset_service.save_json(
            config
            .RECOMMENDATIONS_PATH,

            [
                item.model_dump(
                    mode="json"
                )

                for item
                in recommendations
            ],
        )

        analytics = (
            self._build_analytics(
                requirements=(
                    requirements
                ),

                intelligence=(
                    intelligence
                ),

                evidence=(
                    evidence
                ),

                assessments=(
                    assessments
                ),

                gaps=(
                    gaps
                ),

                recommendations=(
                    recommendations
                ),
            )
        )

        self.dataset_service.save_json(
            config.ANALYTICS_PATH,
            analytics,
        )

        self._append_analysis_history(
            analytics
        )

        return {
            "requirements":
                len(
                    requirements
                ),

            "rvus":
                len(
                    rvus
                ),

            "adequacy_assessments":
                len(
                    assessments
                ),

            "adequate_rvus":
                analytics[
                    "overview"
                ][
                    "adequate_rvus"
                ],

            "validated_rvus":
                analytics[
                    "overview"
                ][
                    "validated_rvus"
                ],

            "overall_rvc":
                analytics[
                    "overview"
                ][
                    "overall_rvc"
                ],

            "execution_confirmed_percent":
                analytics[
                    "overview"
                ][
                    "execution_confirmed_percent"
                ],

            "average_rves":
                analytics[
                    "overview"
                ][
                    "avg_rves"
                ],

            "gaps":
                len(
                    gaps
                ),

            "recommendations":
                len(
                    recommendations
                ),
        }

    def run_revalidation(
        self,
    ):
        if not (
            config
            .REVALIDATION_INPUT_PATH
            .exists()
        ):
            return []

        raw = (
            self.dataset_service
            .load_json(
                config
                .REVALIDATION_INPUT_PATH
            )
        )

        cases = TypeAdapter(
            list[
                RevalidationChangeCase
            ]
        ).validate_python(
            raw
        )

        reports = [
            self.revalidation_service
            .analyze(
                case
            )

            for case
            in cases
        ]

        self.dataset_service.save_json(
            config
            .REVALIDATION_RESULTS_PATH,

            [
                report.model_dump(
                    mode="json"
                )

                for report
                in reports
            ],
        )

        return reports

    def _build_analytics(
        self,
        *,
        requirements,
        intelligence,
        evidence,
        assessments,
        gaps,
        recommendations,
    ):
        generated_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        intelligence_map = {
            item.requirement_id:
                item

            for item
            in intelligence
        }

        total_rvus = sum(
            item.total_rvus

            for item
            in intelligence
        )

        total_supported_rvus = sum(
            item.supported_rvus

            for item
            in intelligence
        )

        not_assessed_rvus = sum(
            item.not_assessed_rvus

            for item
            in intelligence
        )

        adequate_rvus = sum(
            item.adequate_rvus

            for item
            in intelligence
        )

        validated_rvus = sum(
            item.validated_rvus

            for item
            in intelligence
        )

        overall_rvc = (
            adequate_rvus
            / total_rvus
            * 100

            if total_rvus
            else 0.0
        )

        assessable_adequacy = (
            adequate_rvus
            / total_supported_rvus
            * 100

            if total_supported_rvus
            else 0.0
        )

        execution_confirmed = (
            validated_rvus
            / total_supported_rvus
            * 100

            if total_supported_rvus
            else 0.0
        )

        assessed = [
            item

            for item
            in intelligence

            if (
                item.validation_status
                != "NOT_ASSESSED"
            )
        ]

        avg_rves = (
            sum(
                item.rves

                for item
                in assessed
            )
            / len(
                assessed
            )

            if assessed
            else 0.0
        )

        adequate_requirements = sum(
            item.validation_status
            == "ADEQUATE"

            for item
            in intelligence
        )

        partial_requirements = sum(
            item.validation_status
            == "PARTIAL"

            for item
            in intelligence
        )

        inadequate_requirements = sum(
            item.validation_status
            == "INADEQUATE"

            for item
            in intelligence
        )

        not_assessed_requirements = sum(
            item.validation_status
            == "NOT_ASSESSED"

            for item
            in intelligence
        )

        requirement_rows = []

        for requirement in (
            requirements
        ):
            result = (
                intelligence_map.get(
                    requirement
                    .requirement_id
                )
            )

            if result is None:
                continue

            requirement_rows.append(
                {
                    **requirement
                    .model_dump(
                        mode="json"
                    ),

                    "total_rvus":
                        result
                        .total_rvus,

                    "supported_rvus":
                        result
                        .supported_rvus,

                    "not_assessed_rvus":
                        result
                        .not_assessed_rvus,

                    "evidence_found_rvus":
                        result
                        .evidence_found_rvus,

                    "adequate_rvus":
                        result
                        .adequate_rvus,

                    "validated_rvus":
                        result
                        .validated_rvus,

                    "rvc_percent":
                        result
                        .rvc_percent,

                    "assessable_adequacy_percent":
                        result
                        .assessable_adequacy_percent,

                    "execution_confirmed_percent":
                        result
                        .execution_confirmed_percent,

                    "rves":
                        result.rves,

                    "rves_factors":
                        result
                        .rves_factors,

                    "rves_experimental":
                        result
                        .rves_experimental,

                    "status":
                        result
                        .validation_status,
                }
            )

        priority_attention = sorted(
            [
                item

                for item
                in requirement_rows

                if (
                    item["risk"]
                    == "HIGH"

                    and (
                        item["status"]
                        != "ADEQUATE"
                    )
                )
            ],

            key=lambda item:
                item[
                    "rvc_percent"
                ],
        )[:6]

        evidence_type_counts = Counter(
            item.evidence_type

            for item
            in evidence
        )

        automated = [
            item

            for item
            in evidence

            if (
                item.evidence_type
                == "AUTOMATED_TEST"
            )
        ]

        performance = [
            item

            for item
            in evidence

            if (
                item.evidence_type
                == "PERFORMANCE_EVIDENCE"
            )
        ]

        manual = [
            item

            for item
            in evidence

            if (
                item.evidence_type
                == "MANUAL_TEST"
            )
        ]

        def count_status(
            items,
            status,
        ):
            return sum(
                1

                for item
                in items

                if (
                    item.execution_status
                    == status
                )
            )

        automated_unmapped = sum(
            1

            for item
            in automated

            if not (
                item.execution_status
            )
        )

        performance_unmapped = sum(
            1

            for item
            in performance

            if not (
                item.execution_status
            )
        )

        manual_not_executed = sum(
            1

            for item
            in manual

            if (
                item.execution_status
                in {
                    None,
                    "NOT_EXECUTED",
                }
            )
        )

        manual_pass = (
            count_status(
                manual,
                "PASS",
            )
        )

        manual_fail = (
            count_status(
                manual,
                "FAIL",
            )
        )

        manual_blocked = (
            count_status(
                manual,
                "BLOCKED",
            )
        )

        manual_skipped = (
            count_status(
                manual,
                "SKIPPED",
            )
        )

        manual_observed_pass = sum(
            1

            for item
            in manual

            if (
                item.execution_status
                == "PASS"

                and self
                ._is_observed_manual_execution(
                    item
                )
            )
        )

        manual_controlled_pass = (
            manual_pass
            - manual_observed_pass
        )

        gap_distribution = dict(
            sorted(
                Counter(
                    item.gap_type

                    for item
                    in gaps
                ).items(),

                key=lambda pair:
                    pair[1],

                reverse=True,
            )
        )

        top_validation_details = []

        seen = set()

        severity_rank = {
            "HIGH":
                0,

            "MEDIUM":
                1,

            "LOW":
                2,
        }

        sorted_gaps = sorted(
            gaps,

            key=lambda item: (
                severity_rank.get(
                    item.severity,
                    9,
                ),

                item.requirement_id,

                item.gap_type,
            ),
        )

        for gap in sorted_gaps:
            key = (
                gap.requirement_id,
                gap.gap_type,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            top_validation_details.append(
                {
                    "issue":
                        gap.description,

                    "gap_type":
                        gap.gap_type,

                    "severity":
                        gap.severity,

                    "requirement_id":
                        gap.requirement_id,

                    "rvu_id":
                        gap.rvu_id,
                }
            )

            if (
                len(
                    top_validation_details
                )
                >= 8
            ):
                break

        strong_candidates = sum(
            item.relevance_score
            >= 0.70

            for item
            in assessments
        )

        moderate_candidates = sum(
            (
                0.40
                <= item.relevance_score
                < 0.70
            )

            for item
            in assessments
        )

        weak_candidates = sum(
            item.relevance_score
            < 0.40

            for item
            in assessments
        )

        return {
            "overview": {
                "generated_at":
                    generated_at,

                "total_requirements":
                    len(
                        requirements
                    ),

                "total_rvus":
                    total_rvus,

                "total_supported_rvus":
                    total_supported_rvus,

                "not_assessed_rvus":
                    not_assessed_rvus,

                "adequate_rvus":
                    adequate_rvus,

                "validated_rvus":
                    validated_rvus,

                "overall_rvc":
                    round(
                        overall_rvc,
                        2,
                    ),

                "assessable_adequacy_percent":
                    round(
                        assessable_adequacy,
                        2,
                    ),

                "execution_confirmed_percent":
                    round(
                        execution_confirmed,
                        2,
                    ),

                "adequately_validated_requirements":
                    adequate_requirements,

                "partial_requirements":
                    partial_requirements,

                "inadequate_requirements":
                    inadequate_requirements,

                "not_assessed_requirements":
                    not_assessed_requirements,

                "avg_rves":
                    round(
                        avg_rves,
                        4,
                    ),

                "rves_experimental":
                    True,

                "priority_attention":
                    priority_attention,

                "gap_distribution":
                    gap_distribution,

                "top_validation_details":
                    top_validation_details,
            },

            "requirements":
                requirement_rows,

            "reports": {
    "generated_at":
        generated_at,

    "evidence_summary": {
        "total_evidence_items":
            len(evidence),

        "automated_tests":
            evidence_type_counts.get(
                "AUTOMATED_TEST",
                0,
            ),

        "manual_tests":
            evidence_type_counts.get(
                "MANUAL_TEST",
                0,
            ),

        "performance_evidence":
            evidence_type_counts.get(
                "PERFORMANCE_EVIDENCE",
                0,
            ),
    },

    "candidate_quality_summary": {
        "strong":
            strong_candidates,

        "moderate":
            moderate_candidates,

        "weak":
            weak_candidates,
    },

    "execution_summary": {
        "automated_pass":
            count_status(
                automated,
                "PASS",
            ),

        "automated_fail":
            count_status(
                automated,
                "FAIL",
            ),

        "automated_skipped":
            count_status(
                automated,
                "SKIPPED",
            ),

        "automated_unmapped":
            automated_unmapped,

        "performance_pass":
            count_status(
                performance,
                "PASS",
            ),

        "performance_fail":
            count_status(
                performance,
                "FAIL",
            ),

        "performance_skipped":
            count_status(
                performance,
                "SKIPPED",
            ),

        "performance_unmapped":
            performance_unmapped,

        "manual_not_executed":
            manual_not_executed,
    },

    "validation_summary": {
        "total_rvus":
            total_rvus,

        "adequate_rvus":
            adequate_rvus,

        "validated_rvus":
            validated_rvus,

        "not_assessed_rvus":
            not_assessed_rvus,

        "overall_rvc":
            round(
                overall_rvc,
                2,
            ),

        "execution_confirmed_percent":
            round(
                execution_confirmed,
                2,
            ),
    },

    "recommendation_summary": {
        "total":
            len(
                recommendations
            ),

        "critical":
            sum(
                item.severity
                == "HIGH"
                for item
                in gaps
            ),

        "important":
            sum(
                item.severity
                == "MEDIUM"
                for item
                in gaps
            ),

        "informational":
            sum(
                item.severity
                == "LOW"
                for item
                in gaps
            ),
    },

    "report_information": {
        "generated_at":
            generated_at,

        "total_requirements":
            len(requirements),

        "analysis_scope":
            "All Component 3 requirements",

        "data_source": (
            "Requirements, RVUs, normalized QA "
            "evidence, execution results and "
            "controlled research fixtures"
        ),
    },
},
        }

    def _is_observed_manual_execution(
        self,
        evidence:
        ValidationEvidence,
    ) -> bool:
        """
        Return True only for real observed
        manual PASS execution evidence.
        """

        if (
            evidence.evidence_type
            != "MANUAL_TEST"
        ):
            return False

        if (
            evidence.execution_status
            != "PASS"
        ):
            return False

        if evidence.synthetic:
            return False

        manual_execution = (
            evidence.metadata.get(
                "manual_execution"
            )
        )

        if not isinstance(
            manual_execution,
            dict,
        ):
            return False

        if (
            manual_execution.get(
                "synthetic",
                True,
            )
        ):
            return False

        return bool(
            manual_execution.get(
                "executed_at"
            )

            and manual_execution.get(
                "executed_by"
            )

            and manual_execution.get(
                "actual_result"
            )
        )

    def _append_analysis_history(
        self,
        analytics,
    ) -> None:
        history = (
            self._load_if_exists(
                config
                .ANALYSIS_HISTORY_PATH
            )
        )

        if not isinstance(
            history,
            list,
        ):
            history = []

        overview = (
            analytics[
                "overview"
            ]
        )

        history.append(
            {
                "generated_at":
                    overview[
                        "generated_at"
                    ],

                "overall_rvc":
                    overview[
                        "overall_rvc"
                    ],

                "avg_rves":
                    overview[
                        "avg_rves"
                    ],

                "adequate_rvus":
                    overview[
                        "adequate_rvus"
                    ],

                "validated_rvus":
                    overview[
                        "validated_rvus"
                    ],

                "execution_confirmed_percent":
                    overview[
                        "execution_confirmed_percent"
                    ],
            }
        )

        history = (
            history[
                -12:
            ]
        )

        self.dataset_service.save_json(
            config
            .ANALYSIS_HISTORY_PATH,

            history,
        )

    def _load_if_exists(
        self,
        path,
    ):
        if not (
            path.exists()
        ):
            return []

        return (
            self.dataset_service
            .load_json(
                path
            )
        )