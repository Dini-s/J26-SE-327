from __future__ import annotations

from collections import (
    Counter,
    defaultdict,
)

from datetime import (
    datetime,
    timezone,
)

import math
import statistics
import time

from typing import Any

from agents.quality_agent import (
    config,
)

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)


class EvaluationService:
    REQUIRED_SECTIONS = (
        "rvu_extraction",
        "evidence_profiles",
        "normalization",
        "retrieval",
        "adequacy",
        "rvc",
        "rves",
        "gap_reviews",
        "revalidation",
    )

    ADEQUACY_CLASSES = (
        "ADEQUATE",
        "PARTIAL",
        "INADEQUATE",
    )

    REVALIDATION_CLASSES = (
        "REUSABLE",
        "MODIFICATION_REQUIRED",
        "OUTDATED",
        "NEW_EVIDENCE_REQUIRED",
    )

    def __init__(
        self,
        agent=None,
    ):
        self.agent = agent

        self.dataset_service = (
            DatasetService()
        )

    def run(
        self,
    ) -> dict[str, Any]:
        if not (
            config
            .EVALUATION_GOLD_PATH
            .exists()
        ):
            raise FileNotFoundError(
                (
                    "Evaluation gold file "
                    "does not exist: "
                    f"{config.EVALUATION_GOLD_PATH}"
                )
            )

        gold = (
            self.dataset_service
            .load_json(
                config
                .EVALUATION_GOLD_PATH
            )
        )

        result = {
            "schema_version":
                "1.0",

            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "readiness":
                self._readiness(
                    gold
                ),

            "rvu_extraction":
                self._evaluate_rvus(
                    gold.get(
                        "rvu_extraction",
                        [],
                    )
                ),

            "evidence_profiles":
                self._evaluate_profiles(
                    gold.get(
                        "evidence_profiles",
                        [],
                    )
                ),

            "normalization":
                self
                ._evaluate_normalization(
                    gold.get(
                        "normalization",
                        [],
                    )
                ),

            "retrieval":
                self._evaluate_retrieval(
                    gold.get(
                        "retrieval",
                        [],
                    )
                ),

            "adequacy":
                self._evaluate_adequacy(
                    gold.get(
                        "adequacy",
                        [],
                    )
                ),

            "rvc":
                self._evaluate_rvc(
                    gold.get(
                        "rvc",
                        [],
                    )
                ),

            "rves":
                self._evaluate_rves(
                    gold.get(
                        "rves",
                        [],
                    )
                ),

            "gap_reviews":
                self._evaluate_gaps(
                    gold.get(
                        "gap_reviews",
                        [],
                    )
                ),

            "revalidation":
                self
                ._evaluate_revalidation(
                    gold.get(
                        "revalidation",
                        [],
                    )
                ),
        }

        self.dataset_service.save_json(
            config
            .EVALUATION_RESULTS_PATH,

            result,
        )

        return result

    def _readiness(
        self,
        gold: dict[
            str,
            Any,
        ],
    ) -> dict[str, Any]:
        missing = []

        counts = {}

        for section in (
            self.REQUIRED_SECTIONS
        ):
            value = gold.get(
                section
            )

            count = (
                len(value)
                if isinstance(
                    value,
                    list,
                )
                else 0
            )

            counts[
                section
            ] = count

            if count == 0:
                missing.append(
                    section
                )

        return {
            "status": (
                "READY"
                if not missing
                else "INCOMPLETE"
            ),

            "missing_sections":
                missing,

            "label_counts":
                counts,
        }

    def _evaluate_rvus(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        rvus = self._load(
            config.RVUS_PATH
        )

        by_ac = defaultdict(
            list
        )

        for rvu in rvus:
            by_ac[
                rvu["ac_id"]
            ].append(
                rvu
            )

        count_matches = 0

        behavior_hits = 0
        behavior_total = 0

        provenance_complete = 0
        provenance_total = 0

        evaluated_rvus = 0
        requires_review = 0

        details = []

        for item in gold_items:
            ac_id = item[
                "ac_id"
            ]

            predicted = (
                by_ac.get(
                    ac_id,
                    [],
                )
            )

            expected_count = int(
                item[
                    "expected_rvu_count"
                ]
            )

            actual_count = len(
                predicted
            )

            exact_count = (
                actual_count
                == expected_count
            )

            if exact_count:
                count_matches += 1

            gold_behaviors = [
                str(value).upper()

                for value
                in item.get(
                    "expected_behavior_types",
                    [],
                )
            ]

            predicted_behaviors = [
                str(
                    value.get(
                        "behavior_type",
                        "",
                    )
                ).upper()

                for value
                in predicted
            ]

            gold_counter = Counter(
                gold_behaviors
            )

            predicted_counter = (
                Counter(
                    predicted_behaviors
                )
            )

            matched = sum(
                min(
                    gold_counter[
                        label
                    ],

                    predicted_counter[
                        label
                    ],
                )

                for label
                in gold_counter
            )

            behavior_hits += (
                matched
            )

            behavior_total += len(
                gold_behaviors
            )

            for rvu in predicted:
                evaluated_rvus += 1

                if rvu.get(
                    "requires_review",
                    False,
                ):
                    requires_review += 1

                fields = (
                    "requirement_id",
                    "ac_id",
                    "source_text",
                    "source_fragment",
                    "source_span",
                    "extraction_method",
                )

                provenance_total += 1

                if all(
                    rvu.get(
                        field
                    )
                    not in (
                        None,
                        "",
                        {},
                    )

                    for field
                    in fields
                ):
                    provenance_complete += 1

            details.append(
                {
                    "ac_id":
                        ac_id,

                    "expected_rvu_count":
                        expected_count,

                    "actual_rvu_count":
                        actual_count,

                    "count_exact":
                        exact_count,

                    "expected_behavior_types":
                        gold_behaviors,

                    "predicted_behavior_types":
                        predicted_behaviors,
                }
            )

        return {
            "status":
                "EVALUATED",

            "cases":
                len(
                    gold_items
                ),

            "atomicity_count_accuracy":
                round(
                    self._safe_div(
                        count_matches,
                        len(
                            gold_items
                        ),
                    ),
                    4,
                ),

            "behavior_recall":
                round(
                    self._safe_div(
                        behavior_hits,
                        behavior_total,
                    ),
                    4,
                ),

            "provenance_completeness":
                round(
                    self._safe_div(
                        provenance_complete,
                        provenance_total,
                    ),
                    4,
                ),

            "requires_review_rate":
                round(
                    self._safe_div(
                        requires_review,
                        evaluated_rvus,
                    ),
                    4,
                ),

            "details":
                details,
        }

    def _evaluate_profiles(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        profiles = self._load(
            config
            .EVIDENCE_PROFILES_PATH
        )

        profile_map = {
            item[
                "rvu_id"
            ]:
            item

            for item
            in profiles
        }

        list_fields = (
            "required_scenarios",
            "preconditions",
            "inputs",
            "expected_outcomes",
            "required_assertions",
        )

        scalar_fields = (
            "evidence_type",
            "metric",
            "percentile",
            "operator",
            "threshold",
            "unit",
            "load",
            "duration_seconds",
            "scope",
            "support_status",
        )

        field_scores = []

        missing_profiles = []

        details = []

        for item in gold_items:
            rvu_id = item[
                "rvu_id"
            ]

            predicted = (
                profile_map.get(
                    rvu_id
                )
            )

            if predicted is None:
                missing_profiles.append(
                    rvu_id
                )

                continue

            expected = (
                item.get(
                    "expected",
                    {},
                )
            )

            scores = {}

            for field in list_fields:
                if field not in expected:
                    continue

                score = self._set_f1(
                    expected.get(
                        field,
                        [],
                    ),

                    predicted.get(
                        field,
                        [],
                    ),
                )

                scores[
                    field
                ] = score

                field_scores.append(
                    score
                )

            for field in scalar_fields:
                if field not in expected:
                    continue

                score = (
                    1.0
                    if self
                    ._scalar_equal(
                        expected.get(
                            field
                        ),

                        predicted.get(
                            field
                        ),
                    )
                    else 0.0
                )

                scores[
                    field
                ] = score

                field_scores.append(
                    score
                )

            details.append(
                {
                    "rvu_id":
                        rvu_id,

                    "field_scores":
                        scores,
                }
            )

        return {
            "status":
                "EVALUATED",

            "cases":
                len(
                    gold_items
                ),

            "covered_cases":
                (
                    len(
                        gold_items
                    )
                    - len(
                        missing_profiles
                    )
                ),

            "field_level_agreement":
                round(
                    self._mean(
                        field_scores
                    ),
                    4,
                ),

            "missing_profiles":
                missing_profiles,

            "details":
                details,
        }

    def _evaluate_normalization(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        evidence = self._load(
            config
            .NORMALIZED_EVIDENCE_PATH
        )

        evidence_map = {
            item[
                "evidence_id"
            ]:
            item

            for item
            in evidence
        }

        hits = 0
        total = 0

        missing = []

        field_hits = defaultdict(
            int
        )

        field_totals = defaultdict(
            int
        )

        details = []

        for item in gold_items:
            evidence_id = item[
                "evidence_id"
            ]

            predicted = (
                evidence_map.get(
                    evidence_id
                )
            )

            if predicted is None:
                missing.append(
                    evidence_id
                )

                continue

            expected = item.get(
                "expected",
                {},
            )

            result_fields = {}

            for field, value in (
                expected.items()
            ):
                field_totals[
                    field
                ] += 1

                total += 1

                if (
                    field
                    == "source_path_contains"
                ):
                    actual_match = (
                        str(value).lower()
                        in str(
                            predicted.get(
                                "source_path",
                                "",
                            )
                        ).lower()
                    )

                else:
                    actual_match = (
                        self._scalar_equal(
                            value,

                            predicted.get(
                                field
                            ),
                        )
                    )

                result_fields[
                    field
                ] = actual_match

                if actual_match:
                    hits += 1
                    field_hits[
                        field
                    ] += 1

            details.append(
                {
                    "evidence_id":
                        evidence_id,

                    "field_matches":
                        result_fields,
                }
            )

        field_accuracy = {
            field:
                round(
                    self._safe_div(
                        field_hits[
                            field
                        ],

                        field_totals[
                            field
                        ],
                    ),
                    4,
                )

            for field
            in field_totals
        }

        return {
            "status":
                "EVALUATED",

            "cases":
                len(
                    gold_items
                ),

            "field_extraction_accuracy":
                round(
                    self._safe_div(
                        hits,
                        total,
                    ),
                    4,
                ),

            "field_accuracy":
                field_accuracy,

            "missing_evidence":
                missing,

            "details":
                details,
        }

    def _evaluate_retrieval(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        if self.agent is None:
            return {
                "status":
                    "ERROR",

                "message":
                    (
                        "EvaluationService requires "
                        "a QualityAgent instance for "
                        "retrieval evaluation."
                    ),
            }

        methods = (
            "keyword",
            "tfidf",
            "semantic",
        )

        method_rows = {
            method: []

            for method
            in methods
        }

        for item in gold_items:
            rvu_id = item[
                "rvu_id"
            ]

            relevant = set(
                item.get(
                    "relevant_evidence_ids",
                    [],
                )
            )

            k = int(
                item.get(
                    "k",
                    config.TOP_K,
                )
            )

            for method in methods:
                started = (
                    time.perf_counter()
                )

                matches = (
                    self.agent
                    .retrieve(
                        rvu_id=rvu_id,
                        method=method,
                        top_k=k,
                    )
                )

                elapsed_ms = (
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000.0
                )

                ranked = [
                    match.evidence_id

                    for match
                    in matches
                ]

                retrieved = set(
                    ranked
                )

                true_positive = len(
                    retrieved
                    & relevant
                )

                precision = (
                    self._safe_div(
                        true_positive,
                        len(
                            ranked
                        ),
                    )
                )

                recall = (
                    self._safe_div(
                        true_positive,
                        len(
                            relevant
                        ),
                    )
                )

                f1 = self._f1(
                    precision,
                    recall,
                )

                reciprocal_rank = 0.0

                for rank, evidence_id in (
                    enumerate(
                        ranked,
                        start=1,
                    )
                ):
                    if (
                        evidence_id
                        in relevant
                    ):
                        reciprocal_rank = (
                            1.0
                            / rank
                        )

                        break

                method_rows[
                    method
                ].append(
                    {
                        "rvu_id":
                            rvu_id,

                        "k":
                            k,

                        "precision_at_k":
                            precision,

                        "recall_at_k":
                            recall,

                        "f1_at_k":
                            f1,

                        "reciprocal_rank":
                            reciprocal_rank,

                        "latency_ms":
                            elapsed_ms,

                        "ranked_evidence_ids":
                            ranked,
                    }
                )

        output = {
            "status":
                "EVALUATED",

            "query_count":
                len(
                    gold_items
                ),

            "methods":
                {},
        }

        for method, rows in (
            method_rows.items()
        ):
            latencies = [
                row[
                    "latency_ms"
                ]

                for row
                in rows
            ]

            output[
                "methods"
            ][
                method
            ] = {
                "precision_at_k":
                    round(
                        self._mean(
                            [
                                row[
                                    "precision_at_k"
                                ]
                                for row
                                in rows
                            ]
                        ),
                        4,
                    ),

                "recall_at_k":
                    round(
                        self._mean(
                            [
                                row[
                                    "recall_at_k"
                                ]
                                for row
                                in rows
                            ]
                        ),
                        4,
                    ),

                "f1_at_k":
                    round(
                        self._mean(
                            [
                                row[
                                    "f1_at_k"
                                ]
                                for row
                                in rows
                            ]
                        ),
                        4,
                    ),

                "mrr":
                    round(
                        self._mean(
                            [
                                row[
                                    "reciprocal_rank"
                                ]
                                for row
                                in rows
                            ]
                        ),
                        4,
                    ),

                "latency_p50_ms":
                    round(
                        self._percentile(
                            latencies,
                            50,
                        ),
                        3,
                    ),

                "latency_p95_ms":
                    round(
                        self._percentile(
                            latencies,
                            95,
                        ),
                        3,
                    ),

                "queries":
                    rows,
            }

        return output

    def _evaluate_adequacy(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        assessments = self._load(
            config
            .ADEQUACY_ASSESSMENTS_PATH
        )

        assessment_map = {
            (
                item["rvu_id"],
                item["evidence_id"],
            ):
            item

            for item
            in assessments
        }

        gold_labels = []
        predicted_labels = []

        missing = []

        reviewer_a = []
        reviewer_b = []

        for item in gold_items:
            key = (
                item[
                    "rvu_id"
                ],

                item[
                    "evidence_id"
                ],
            )

            assessment = (
                assessment_map.get(
                    key
                )
            )

            if assessment is None:
                missing.append(
                    {
                        "rvu_id":
                            key[0],

                        "evidence_id":
                            key[1],
                    }
                )

                continue

            gold_label = (
                str(
                    item[
                        "gold_label"
                    ]
                ).upper()
            )

            predicted_label = (
                str(
                    assessment[
                        "adequacy_status"
                    ]
                ).upper()
            )

            if (
                gold_label
                not in
                self.ADEQUACY_CLASSES
            ):
                continue

            if (
                predicted_label
                not in
                self.ADEQUACY_CLASSES
            ):
                predicted_label = (
                    "INADEQUATE"
                )

            gold_labels.append(
                gold_label
            )

            predicted_labels.append(
                predicted_label
            )

            labels = [
                str(
                    label.get(
                        "label",
                        "",
                    )
                ).upper()

                for label
                in item.get(
                    "reviewer_labels",
                    [],
                )

                if label.get(
                    "label"
                )
            ]

            if len(labels) >= 2:
                reviewer_a.append(
                    labels[0]
                )

                reviewer_b.append(
                    labels[1]
                )

        metrics = (
            self
            ._classification_metrics(
                gold_labels,
                predicted_labels,
                self.ADEQUACY_CLASSES,
            )
        )

        non_adequate = sum(
            1
            for label
            in gold_labels
            if (
                label
                != "ADEQUATE"
            )
        )

        false_adequate = sum(
            1

            for gold_label,
            predicted_label

            in zip(
                gold_labels,
                predicted_labels,
            )

            if (
                gold_label
                != "ADEQUATE"
                and
                predicted_label
                == "ADEQUATE"
            )
        )

        metrics.update(
            {
                "status":
                    "EVALUATED",

                "covered_pairs":
                    len(
                        gold_labels
                    ),

                "missing_pairs":
                    missing,

                "false_adequate_count":
                    false_adequate,

                "false_adequate_rate":
                    round(
                        self._safe_div(
                            false_adequate,
                            non_adequate,
                        ),
                        4,
                    ),

                "reviewer_cohen_kappa":
                    self._round_or_none(
                        self._cohen_kappa(
                            reviewer_a,
                            reviewer_b,
                        )
                    ),
            }
        )

        return metrics

    def _evaluate_rvc(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        intelligence = self._load(
            config
            .REQUIREMENT_INTELLIGENCE_PATH
        )

        result_map = {
            item[
                "requirement_id"
            ]:
            item

            for item
            in intelligence
        }

        predicted_values = []
        expert_values = []

        status_hits = 0
        status_total = 0

        missing = []

        details = []

        for item in gold_items:
            requirement_id = item[
                "requirement_id"
            ]

            predicted = (
                result_map.get(
                    requirement_id
                )
            )

            if predicted is None:
                missing.append(
                    requirement_id
                )

                continue

            expert_rvc = float(
                item[
                    "expert_rvc_percent"
                ]
            )

            predicted_rvc = float(
                predicted[
                    "rvc_percent"
                ]
            )

            expert_values.append(
                expert_rvc
            )

            predicted_values.append(
                predicted_rvc
            )

            expert_status = item.get(
                "expert_status"
            )

            if expert_status:
                status_total += 1

                if (
                    str(
                        predicted.get(
                            "validation_status",
                            "",
                        )
                    ).upper()
                    ==
                    str(
                        expert_status
                    ).upper()
                ):
                    status_hits += 1

            details.append(
                {
                    "requirement_id":
                        requirement_id,

                    "expert_rvc_percent":
                        expert_rvc,

                    "predicted_rvc_percent":
                        predicted_rvc,

                    "absolute_error":
                        abs(
                            expert_rvc
                            - predicted_rvc
                        ),
                }
            )

        mae = self._mean(
            [
                abs(
                    expert
                    - predicted
                )

                for expert,
                predicted

                in zip(
                    expert_values,
                    predicted_values,
                )
            ]
        )

        return {
            "status":
                "EVALUATED",

            "cases":
                len(
                    predicted_values
                ),

            "mae":
                round(
                    mae,
                    4,
                ),

            "pearson_correlation":
                self._round_or_none(
                    self._pearson(
                        expert_values,
                        predicted_values,
                    )
                ),

            "spearman_correlation":
                self._round_or_none(
                    self._spearman(
                        expert_values,
                        predicted_values,
                    )
                ),

            "status_accuracy":
                round(
                    self._safe_div(
                        status_hits,
                        status_total,
                    ),
                    4,
                ),

            "missing_requirements":
                missing,

            "details":
                details,
        }

    def _evaluate_rves(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        intelligence = self._load(
            config
            .REQUIREMENT_INTELLIGENCE_PATH
        )

        result_map = {
            item[
                "requirement_id"
            ]:
            item

            for item
            in intelligence
        }

        rows = []

        missing = []

        for item in gold_items:
            requirement_id = item[
                "requirement_id"
            ]

            predicted = (
                result_map.get(
                    requirement_id
                )
            )

            if predicted is None:
                missing.append(
                    requirement_id
                )

                continue

            rows.append(
                {
                    "requirement_id":
                        requirement_id,

                    "expert_strength":
                        float(
                            item[
                                "expert_strength"
                            ]
                        ),

                    "production_rves":
                        float(
                            predicted[
                                "rves"
                            ]
                        ),

                    "factors":
                        predicted.get(
                            "rves_factors",
                            {},
                        ),
                }
            )

        experts = [
            row[
                "expert_strength"
            ]
            for row
            in rows
        ]

        production = [
            row[
                "production_rves"
            ]
            for row
            in rows
        ]

        baseline = {
            "mae":
                round(
                    self._mean(
                        [
                            abs(
                                expert
                                - predicted
                            )

                            for expert,
                                predicted

                            in zip(
                                experts,
                                production,
                            )
                        ]
                    ),
                    4,
                ),

            "spearman":
                self._round_or_none(
                    self._spearman(
                        experts,
                        production,
                    )
                ),
        }

        weight_sets = {
            "equal": {
                "R_relevance":
                    0.25,

                "A_adequacy":
                    0.25,

                "C_completeness":
                    0.25,

                "E_execution":
                    0.25,
            },
        }

        factors = (
            "R_relevance",
            "A_adequacy",
            "C_completeness",
            "E_execution",
        )

        for omitted in factors:
            weight_sets[
                f"ablate_{omitted}"
            ] = {
                factor: (
                    0.0
                    if factor
                    == omitted
                    else
                    1.0 / 3.0
                )

                for factor
                in factors
            }

        for primary in factors:
            for primary_weight in (
                0.10,
                0.20,
                0.30,
                0.40,
            ):
                remaining = (
                    (
                        1.0
                        - primary_weight
                    )
                    / 3.0
                )

                weight_sets[
                    (
                        f"sensitivity_"
                        f"{primary}_"
                        f"{primary_weight:.2f}"
                    )
                ] = {
                    factor: (
                        primary_weight
                        if factor
                        == primary
                        else remaining
                    )

                    for factor
                    in factors
                }

        experiments = {}

        for name, weights in (
            weight_sets.items()
        ):
            predicted_scores = [
                self._weighted_score(
                    row[
                        "factors"
                    ],
                    weights,
                )

                for row
                in rows
            ]

            experiments[
                name
            ] = {
                "weights":
                    weights,

                "mae":
                    round(
                        self._mean(
                            [
                                abs(
                                    expert
                                    - predicted
                                )

                                for expert,
                                    predicted

                                in zip(
                                    experts,
                                    predicted_scores,
                                )
                            ]
                        ),
                        4,
                    ),

                "spearman":
                    self._round_or_none(
                        self._spearman(
                            experts,
                            predicted_scores,
                        )
                    ),
            }

        return {
            "status":
                "EVALUATED",

            "cases":
                len(
                    rows
                ),

            "production_baseline":
                baseline,

            "weight_experiments":
                experiments,

            "missing_requirements":
                missing,

            "note":
                (
                    "Experimental results do not "
                    "automatically modify production "
                    "RVES weights."
                ),
        }

    def _evaluate_gaps(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        gaps = self._load(
            config.GAPS_PATH
        )

        recommendations = self._load(
            config
            .RECOMMENDATIONS_PATH
        )

        gap_ids = {
            item["gap_id"]
            for item
            in gaps
        }

        recommendation_ids = {
            item[
                "recommendation_id"
            ]
            for item
            in recommendations
        }

        correctness = []
        groundedness = []
        actionability = []

        hallucinations = 0
        invalid_refs = []

        for item in gold_items:
            gap_id = item.get(
                "gap_id"
            )

            recommendation_id = (
                item.get(
                    "recommendation_id"
                )
            )

            if (
                gap_id
                and gap_id
                not in gap_ids
            ):
                invalid_refs.append(
                    gap_id
                )

            if (
                recommendation_id
                and recommendation_id
                not in recommendation_ids
            ):
                invalid_refs.append(
                    recommendation_id
                )

            if (
                item.get(
                    "correctness"
                )
                is not None
            ):
                correctness.append(
                    float(
                        item[
                            "correctness"
                        ]
                    )
                )

            if (
                item.get(
                    "groundedness"
                )
                is not None
            ):
                groundedness.append(
                    float(
                        item[
                            "groundedness"
                        ]
                    )
                )

            if (
                item.get(
                    "actionability"
                )
                is not None
            ):
                actionability.append(
                    float(
                        item[
                            "actionability"
                        ]
                    )
                )

            if item.get(
                "hallucination",
                False,
            ):
                hallucinations += 1

        return {
            "status":
                "EVALUATED",

            "reviews":
                len(
                    gold_items
                ),

            "average_correctness":
                round(
                    self._mean(
                        correctness
                    ),
                    4,
                ),

            "average_groundedness":
                round(
                    self._mean(
                        groundedness
                    ),
                    4,
                ),

            "average_actionability":
                round(
                    self._mean(
                        actionability
                    ),
                    4,
                ),

            "hallucination_count":
                hallucinations,

            "invalid_references":
                sorted(
                    set(
                        invalid_refs
                    )
                ),
        }

    def _evaluate_revalidation(
        self,
        gold_items,
    ):
        if not gold_items:
            return self._empty()

        reports = self._load(
            config
            .REVALIDATION_RESULTS_PATH
        )

        prediction_map = {}

        for report in reports:
            for decision in report.get(
                "decisions",
                [],
            ):
                prediction_map[
                    (
                        report[
                            "change_id"
                        ],

                        decision[
                            "evidence_name"
                        ],
                    )
                ] = (
                    decision[
                        "classification"
                    ]
                )

        gold_labels = []
        predictions = []

        missing = []

        reviewer_a = []
        reviewer_b = []

        for item in gold_items:
            key = (
                item[
                    "change_id"
                ],

                item[
                    "evidence_name"
                ],
            )

            predicted = (
                prediction_map.get(
                    key
                )
            )

            if predicted is None:
                missing.append(
                    {
                        "change_id":
                            key[0],

                        "evidence_name":
                            key[1],
                    }
                )

                continue

            gold_label = (
                str(
                    item[
                        "gold_class"
                    ]
                ).upper()
            )

            predicted_label = (
                str(
                    predicted
                ).upper()
            )

            gold_labels.append(
                gold_label
            )

            predictions.append(
                predicted_label
            )

            labels = [
                str(
                    value.get(
                        "label",
                        "",
                    )
                ).upper()

                for value
                in item.get(
                    "reviewer_labels",
                    [],
                )

                if value.get(
                    "label"
                )
            ]

            if len(labels) >= 2:
                reviewer_a.append(
                    labels[0]
                )

                reviewer_b.append(
                    labels[1]
                )

        metrics = (
            self
            ._classification_metrics(
                gold_labels,
                predictions,
                self.REVALIDATION_CLASSES,
            )
        )

        metrics.update(
            {
                "status":
                    "EVALUATED",

                "covered_decisions":
                    len(
                        gold_labels
                    ),

                "missing_decisions":
                    missing,

                "reviewer_cohen_kappa":
                    self._round_or_none(
                        self._cohen_kappa(
                            reviewer_a,
                            reviewer_b,
                        )
                    ),
            }
        )

        return metrics

    def _load(
        self,
        path,
    ):
        if not path.exists():
            return []

        return (
            self.dataset_service
            .load_json(
                path
            )
        )

    @staticmethod
    def _empty():
        return {
            "status":
                "NO_GOLD_LABELS"
        }

    @staticmethod
    def _safe_div(
        numerator,
        denominator,
    ):
        if not denominator:
            return 0.0

        return (
            float(numerator)
            / float(denominator)
        )

    @staticmethod
    def _mean(
        values,
    ):
        if not values:
            return 0.0

        return float(
            statistics.mean(
                values
            )
        )

    @staticmethod
    def _f1(
        precision,
        recall,
    ):
        if (
            precision
            + recall
            == 0
        ):
            return 0.0

        return (
            2.0
            * precision
            * recall
            / (
                precision
                + recall
            )
        )

    @classmethod
    def _set_f1(
        cls,
        expected,
        actual,
    ):
        expected_set = {
            str(value)
            .strip()
            .lower()

            for value
            in expected
        }

        actual_set = {
            str(value)
            .strip()
            .lower()

            for value
            in actual
        }

        if (
            not expected_set
            and
            not actual_set
        ):
            return 1.0

        if not expected_set:
            return 0.0

        true_positive = len(
            expected_set
            & actual_set
        )

        precision = cls._safe_div(
            true_positive,
            len(
                actual_set
            ),
        )

        recall = cls._safe_div(
            true_positive,
            len(
                expected_set
            ),
        )

        return cls._f1(
            precision,
            recall,
        )

    @staticmethod
    def _scalar_equal(
        expected,
        actual,
    ):
        if (
            expected is None
            and actual is None
        ):
            return True

        if (
            expected is None
            or actual is None
        ):
            return False

        if (
            isinstance(
                expected,
                (int, float),
            )
            and
            isinstance(
                actual,
                (int, float),
            )
        ):
            return math.isclose(
                float(expected),
                float(actual),
                rel_tol=1e-6,
                abs_tol=1e-6,
            )

        return (
            str(expected)
            .strip()
            .lower()
            ==
            str(actual)
            .strip()
            .lower()
        )

    @classmethod
    def _classification_metrics(
        cls,
        gold,
        predicted,
        classes,
    ):
        if not gold:
            return {
                "accuracy":
                    0.0,

                "macro_precision":
                    0.0,

                "macro_recall":
                    0.0,

                "macro_f1":
                    0.0,

                "per_class":
                    {},

                "confusion_matrix":
                    {},
            }

        accuracy = cls._safe_div(
            sum(
                1

                for gold_label,
                    predicted_label

                in zip(
                    gold,
                    predicted,
                )

                if (
                    gold_label
                    == predicted_label
                )
            ),

            len(
                gold
            ),
        )

        per_class = {}

        precisions = []
        recalls = []
        f1_scores = []

        confusion = {
            gold_class: {
                predicted_class: 0

                for predicted_class
                in classes
            }

            for gold_class
            in classes
        }

        for gold_label, predicted_label in (
            zip(
                gold,
                predicted,
            )
        ):
            if (
                gold_label
                in confusion
                and
                predicted_label
                in confusion[
                    gold_label
                ]
            ):
                confusion[
                    gold_label
                ][
                    predicted_label
                ] += 1

        for label in classes:
            true_positive = sum(
                1

                for gold_label,
                    predicted_label

                in zip(
                    gold,
                    predicted,
                )

                if (
                    gold_label
                    == label
                    and
                    predicted_label
                    == label
                )
            )

            false_positive = sum(
                1

                for gold_label,
                    predicted_label

                in zip(
                    gold,
                    predicted,
                )

                if (
                    gold_label
                    != label
                    and
                    predicted_label
                    == label
                )
            )

            false_negative = sum(
                1

                for gold_label,
                    predicted_label

                in zip(
                    gold,
                    predicted,
                )

                if (
                    gold_label
                    == label
                    and
                    predicted_label
                    != label
                )
            )

            precision = cls._safe_div(
                true_positive,
                true_positive
                + false_positive,
            )

            recall = cls._safe_div(
                true_positive,
                true_positive
                + false_negative,
            )

            f1 = cls._f1(
                precision,
                recall,
            )

            precisions.append(
                precision
            )

            recalls.append(
                recall
            )

            f1_scores.append(
                f1
            )

            per_class[
                label
            ] = {
                "precision":
                    round(
                        precision,
                        4,
                    ),

                "recall":
                    round(
                        recall,
                        4,
                    ),

                "f1":
                    round(
                        f1,
                        4,
                    ),

                "support":
                    sum(
                        1
                        for value
                        in gold
                        if (
                            value
                            == label
                        )
                    ),
            }

        return {
            "accuracy":
                round(
                    accuracy,
                    4,
                ),

            "macro_precision":
                round(
                    cls._mean(
                        precisions
                    ),
                    4,
                ),

            "macro_recall":
                round(
                    cls._mean(
                        recalls
                    ),
                    4,
                ),

            "macro_f1":
                round(
                    cls._mean(
                        f1_scores
                    ),
                    4,
                ),

            "per_class":
                per_class,

            "confusion_matrix":
                confusion,
        }

    @staticmethod
    def _pearson(
        x,
        y,
    ):
        if (
            len(x) < 2
            or len(x)
            != len(y)
        ):
            return None

        mean_x = (
            sum(x)
            / len(x)
        )

        mean_y = (
            sum(y)
            / len(y)
        )

        numerator = sum(
            (
                a
                - mean_x
            )
            * (
                b
                - mean_y
            )

            for a, b
            in zip(
                x,
                y,
            )
        )

        denominator_x = math.sqrt(
            sum(
                (
                    value
                    - mean_x
                )
                ** 2

                for value
                in x
            )
        )

        denominator_y = math.sqrt(
            sum(
                (
                    value
                    - mean_y
                )
                ** 2

                for value
                in y
            )
        )

        denominator = (
            denominator_x
            * denominator_y
        )

        if denominator == 0:
            return None

        return (
            numerator
            / denominator
        )

    @classmethod
    def _spearman(
        cls,
        x,
        y,
    ):
        if (
            len(x) < 2
            or len(x)
            != len(y)
        ):
            return None

        return cls._pearson(
            cls._rank(
                x
            ),

            cls._rank(
                y
            ),
        )

    @staticmethod
    def _rank(
        values,
    ):
        ordered = sorted(
            enumerate(
                values
            ),

            key=lambda pair:
                pair[1],
        )

        result = [
            0.0
        ] * len(
            values
        )

        index = 0

        while index < len(
            ordered
        ):
            end = index

            while (
                end + 1
                < len(
                    ordered
                )
                and
                ordered[
                    end + 1
                ][1]
                ==
                ordered[
                    index
                ][1]
            ):
                end += 1

            rank = (
                (
                    index + 1
                    + end + 1
                )
                / 2.0
            )

            for position in range(
                index,
                end + 1,
            ):
                original_index = (
                    ordered[
                        position
                    ][0]
                )

                result[
                    original_index
                ] = rank

            index = (
                end + 1
            )

        return result

    @staticmethod
    def _percentile(
        values,
        percentile,
    ):
        if not values:
            return 0.0

        ordered = sorted(
            float(value)
            for value
            in values
        )

        if len(
            ordered
        ) == 1:
            return ordered[0]

        position = (
            (
                len(ordered)
                - 1
            )
            * (
                percentile
                / 100.0
            )
        )

        lower = math.floor(
            position
        )

        upper = math.ceil(
            position
        )

        if lower == upper:
            return ordered[
                lower
            ]

        fraction = (
            position
            - lower
        )

        return (
            ordered[
                lower
            ]
            * (
                1.0
                - fraction
            )
            +
            ordered[
                upper
            ]
            * fraction
        )

    @staticmethod
    def _cohen_kappa(
        reviewer_a,
        reviewer_b,
    ):
        if (
            len(
                reviewer_a
            )
            < 2
            or
            len(
                reviewer_a
            )
            != len(
                reviewer_b
            )
        ):
            return None

        total = len(
            reviewer_a
        )

        observed = (
            sum(
                1

                for first,
                    second

                in zip(
                    reviewer_a,
                    reviewer_b,
                )

                if first
                == second
            )
            / total
        )

        labels = set(
            reviewer_a
        ) | set(
            reviewer_b
        )

        counts_a = Counter(
            reviewer_a
        )

        counts_b = Counter(
            reviewer_b
        )

        expected = sum(
            (
                counts_a[
                    label
                ]
                / total
            )
            *
            (
                counts_b[
                    label
                ]
                / total
            )

            for label
            in labels
        )

        if math.isclose(
            expected,
            1.0,
        ):
            return 1.0

        return (
            (
                observed
                - expected
            )
            /
            (
                1.0
                - expected
            )
        )

    @staticmethod
    def _weighted_score(
        factors,
        weights,
    ):
        return sum(
            float(
                factors.get(
                    factor,
                    0.0,
                )
            )
            * float(weight)

            for factor,
                weight

            in weights.items()
        )

    @staticmethod
    def _round_or_none(
        value,
    ):
        if value is None:
            return None

        return round(
            float(value),
            4,
        )