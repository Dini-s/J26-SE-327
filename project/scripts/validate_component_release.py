from __future__ import annotations

import argparse
from datetime import (
    datetime,
    timezone,
)

from agents.quality_agent import (
    config,
)

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)


def validate_release(
    strict_evaluation: bool = False,
):
    dataset = DatasetService()

    errors = []
    warnings = []

    required = [
        config.REQUIREMENTS_PATH,
        config.RVUS_PATH,
        config.EVIDENCE_PROFILES_PATH,
        config.NORMALIZED_EVIDENCE_PATH,
        config.ADEQUACY_ASSESSMENTS_PATH,
        config.RVU_ADEQUACY_PATH,
        config.RVU_VALIDATION_PATH,
        config.REQUIREMENT_INTELLIGENCE_PATH,
        config.GAPS_PATH,
        config.RECOMMENDATIONS_PATH,
        config.ANALYTICS_PATH,
        config.REVALIDATION_RESULTS_PATH,
        config.USKG_EXPORT_PATH,
        config.REPRODUCIBILITY_MANIFEST_PATH,
    ]

    for path in required:
        if not path.exists():
            errors.append(
                (
                    "Missing required artifact: "
                    f"{path}"
                )
            )

    if errors:
        result = {
            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "status":
                "FAIL",

            "errors":
                errors,

            "warnings":
                warnings,
        }

        config.ensure_directories()

        dataset.save_json(
            config
            .RELEASE_VALIDATION_PATH,

            result,
        )

        return result

    requirements = (
        dataset
        .load_requirements(
            config
            .REQUIREMENTS_PATH
        )
    )

    rvus = dataset.load_json(
        config.RVUS_PATH
    )

    profiles = (
        dataset.load_json(
            config
            .EVIDENCE_PROFILES_PATH
        )
    )

    evidence = (
        dataset.load_json(
            config
            .NORMALIZED_EVIDENCE_PATH
        )
    )

    assessments = (
        dataset.load_json(
            config
            .ADEQUACY_ASSESSMENTS_PATH
        )
    )

    adequacy = (
        dataset.load_json(
            config
            .RVU_ADEQUACY_PATH
        )
    )

    validations = (
        dataset.load_json(
            config
            .RVU_VALIDATION_PATH
        )
    )

    intelligence = (
        dataset.load_json(
            config
            .REQUIREMENT_INTELLIGENCE_PATH
        )
    )

    gaps = dataset.load_json(
        config.GAPS_PATH
    )

    recommendations = (
        dataset.load_json(
            config
            .RECOMMENDATIONS_PATH
        )
    )

    revalidation = (
        dataset.load_json(
            config
            .REVALIDATION_RESULTS_PATH
        )
    )

    graph = dataset.load_json(
        config.USKG_EXPORT_PATH
    )

    requirement_ids = {
        item.requirement_id

        for item
        in requirements
    }

    rvu_ids = {
        item[
            "rvu_id"
        ]

        for item
        in rvus
    }

    evidence_ids = {
        item[
            "evidence_id"
        ]

        for item
        in evidence
    }

    if len(
        rvu_ids
    ) != len(
        rvus
    ):
        errors.append(
            "Duplicate RVU IDs detected."
        )

    if len(
        evidence_ids
    ) != len(
        evidence
    ):
        errors.append(
            "Duplicate evidence IDs detected."
        )

    profile_rvus = {
        item[
            "rvu_id"
        ]

        for item
        in profiles
    }

    if profile_rvus != rvu_ids:
        errors.append(
            (
                "Expected Evidence Profiles "
                "do not have a one-to-one RVU mapping."
            )
        )

    adequacy_rvus = {
        item[
            "rvu_id"
        ]

        for item
        in adequacy
    }

    if adequacy_rvus != rvu_ids:
        errors.append(
            (
                "RVU adequacy summaries "
                "do not cover every RVU."
            )
        )

    validation_rvus = {
        item[
            "rvu_id"
        ]

        for item
        in validations
    }

    if validation_rvus != rvu_ids:
        errors.append(
            (
                "RVU validation results "
                "do not cover every RVU."
            )
        )

    intelligence_requirements = {
        item[
            "requirement_id"
        ]

        for item
        in intelligence
    }

    if (
        intelligence_requirements
        != requirement_ids
    ):
        errors.append(
            (
                "Requirement intelligence "
                "does not cover all requirements."
            )
        )

    for assessment in (
        assessments
    ):
        if (
            assessment[
                "rvu_id"
            ]
            not in rvu_ids
        ):
            errors.append(
                (
                    "Assessment references unknown "
                    f"RVU {assessment['rvu_id']}"
                )
            )

        if (
            assessment[
                "evidence_id"
            ]
            not in evidence_ids
        ):
            errors.append(
                (
                    "Assessment references unknown "
                    "evidence "
                    f"{assessment['evidence_id']}"
                )
            )

    for item in intelligence:
        total = int(
            item[
                "total_rvus"
            ]
        )

        adequate = int(
            item[
                "adequate_rvus"
            ]
        )

        expected_rvc = (
            (
                adequate
                / total
            )
            * 100.0

            if total
            else 0.0
        )

        actual_rvc = float(
            item[
                "rvc_percent"
            ]
        )

        if (
            abs(
                actual_rvc
                - expected_rvc
            )
            > 0.02
        ):
            errors.append(
                (
                    f"{item['requirement_id']}: "
                    "RVC does not equal "
                    "Adequate RVUs / Total RVUs."
                )
            )

        rves = float(
            item[
                "rves"
            ]
        )

        if not (
            0.0
            <= rves
            <= 1.0
        ):
            errors.append(
                (
                    f"{item['requirement_id']}: "
                    "RVES outside [0, 1]."
                )
            )

    gap_ids = {
        item[
            "gap_id"
        ]

        for item
        in gaps
    }

    for item in recommendations:
        if (
            item[
                "gap_id"
            ]
            not in gap_ids
        ):
            errors.append(
                (
                    "Recommendation references "
                    f"unknown gap {item['gap_id']}"
                )
            )

    revalidation_classes = {
        decision[
            "classification"
        ]

        for report
        in revalidation

        for decision
        in report.get(
            "decisions",
            [],
        )
    }

    expected_classes = {
        "REUSABLE",
        "MODIFICATION_REQUIRED",
        "OUTDATED",
        "NEW_EVIDENCE_REQUIRED",
    }

    missing_classes = (
        expected_classes
        - revalidation_classes
    )

    if missing_classes:
        errors.append(
            (
                "Revalidation does not cover: "
                + ", ".join(
                    sorted(
                        missing_classes
                    )
                )
            )
        )

    graph_node_ids = {
        node[
            "id"
        ]

        for node
        in graph.get(
            "nodes",
            [],
        )
    }

    if len(
        graph_node_ids
    ) != len(
        graph.get(
            "nodes",
            [],
        )
    ):
        errors.append(
            "Duplicate USKG node IDs."
        )

    for edge in graph.get(
        "relationships",
        [],
    ):
        if (
            edge["source"]
            not in graph_node_ids
        ):
            errors.append(
                (
                    "USKG relationship has "
                    "unknown source "
                    f"{edge['source']}"
                )
            )

        if (
            edge["target"]
            not in graph_node_ids
        ):
            errors.append(
                (
                    "USKG relationship has "
                    "unknown target "
                    f"{edge['target']}"
                )
            )

    evaluation_status = (
        "NOT_RUN"
    )

    if (
        config
        .EVALUATION_RESULTS_PATH
        .exists()
    ):
        evaluation = (
            dataset.load_json(
                config
                .EVALUATION_RESULTS_PATH
            )
        )

        evaluation_status = (
            evaluation.get(
                "readiness",
                {},
            ).get(
                "status",
                "UNKNOWN",
            )
        )

        if (
            evaluation_status
            != "READY"
        ):
            message = (
                "Empirical evaluation "
                "gold labels are incomplete."
            )

            if strict_evaluation:
                errors.append(
                    message
                )
            else:
                warnings.append(
                    message
                )

    else:
        message = (
            "Empirical evaluation "
            "has not been run."
        )

        if strict_evaluation:
            errors.append(
                message
            )
        else:
            warnings.append(
                message
            )

    if errors:
        status = "FAIL"

    elif warnings:
        status = (
            "IMPLEMENTATION_READY_"
            "EVALUATION_PENDING"
        )

    else:
        status = (
            "RESEARCH_RELEASE_READY"
        )

    result = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            status,

        "summary": {
            "requirements":
                len(
                    requirements
                ),

            "rvus":
                len(
                    rvus
                ),

            "profiles":
                len(
                    profiles
                ),

            "evidence":
                len(
                    evidence
                ),

            "adequacy_assessments":
                len(
                    assessments
                ),

            "gaps":
                len(
                    gaps
                ),

            "recommendations":
                len(
                    recommendations
                ),

            "revalidation_reports":
                len(
                    revalidation
                ),

            "uskg_nodes":
                len(
                    graph.get(
                        "nodes",
                        [],
                    )
                ),

            "uskg_relationships":
                len(
                    graph.get(
                        "relationships",
                        [],
                    )
                ),

            "evaluation_status":
                evaluation_status,
        },

        "errors":
            errors,

        "warnings":
            warnings,
    }

    dataset.save_json(
        config
        .RELEASE_VALIDATION_PATH,

        result,
    )

    return result


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--strict-evaluation",
        action="store_true",
    )

    args = parser.parse_args()

    result = validate_release(
        strict_evaluation=(
            args
            .strict_evaluation
        )
    )

    print()
    print(
        "=" * 76
    )

    print(
        "ASPIRE COMPONENT 3 "
        "RELEASE VALIDATION"
    )

    print(
        "=" * 76
    )

    print(
        "Status:",
        result[
            "status"
        ],
    )

    print()

    for key, value in (
        result.get(
            "summary",
            {},
        ).items()
    ):
        print(
            f"{key:<28}:",
            value,
        )

    if result[
        "warnings"
    ]:
        print()
        print(
            "Warnings"
        )

        for warning in (
            result[
                "warnings"
            ]
        ):
            print(
                " -",
                warning,
            )

    if result[
        "errors"
    ]:
        print()
        print(
            "Errors"
        )

        for error in (
            result[
                "errors"
            ]
        ):
            print(
                " -",
                error,
            )

    print(
        "=" * 76
    )

    if result[
        "errors"
    ]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()