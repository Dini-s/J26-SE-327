from __future__ import annotations

import argparse

from agents.quality_agent.agent import (
    QualityAgent,
)

from agents.quality_agent.integration.uskg_exporter import (
    C3USKGExporter,
)

from agents.quality_agent.services.evaluation import (
    EvaluationService,
)

from scripts.build_reproducibility_manifest import (
    build_manifest,
)

from scripts.validate_component_release import (
    validate_release,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--strict-evaluation",
        action="store_true",
    )

    args = parser.parse_args()

    print()
    print(
        "=" * 84
    )

    print(
        "ASPIRE COMPONENT 3 "
        "FULL RELEASE PIPELINE"
    )

    print(
        "=" * 84
    )

    agent = QualityAgent()

    print()
    print(
        "[1] Processing requirements "
        "and Expected Evidence Profiles..."
    )

    processing = (
        agent
        .process_requirements()
    )

    print(
        "Requirements:",
        len(
            processing[
                "requirements"
            ]
        ),
    )

    print(
        "RVUs:",
        len(
            processing[
                "rvus"
            ]
        ),
    )

    print(
        "Profiles:",
        len(
            processing[
                "profiles"
            ]
        ),
    )

    print()
    print(
        "[2] Normalizing QA evidence..."
    )

    evidence = (
        agent
        .normalize_evidence()
    )

    print(
        "Evidence:",
        len(
            evidence
        ),
    )

    print()
    print(
        "[3] Running validation "
        "intelligence..."
    )

    analysis = (
        agent
        .analyze_quality()
    )

    print(
        analysis
    )

    print()
    print(
        "[4] Running targeted "
        "revalidation..."
    )

    reports = (
        agent
        .run_revalidation()
    )

    print(
        "Revalidation reports:",
        len(
            reports
        ),
    )

    print()
    print(
        "[5] Exporting C3 USKG..."
    )

    graph = (
        C3USKGExporter()
        .export()
    )

    print(
        "Graph nodes:",
        graph[
            "summary"
        ][
            "node_count"
        ],
    )

    print(
        "Graph relationships:",
        graph[
            "summary"
        ][
            "relationship_count"
        ],
    )

    print()
    print(
        "[6] Running empirical "
        "evaluation..."
    )

    evaluation = (
        EvaluationService(
            agent=agent
        )
        .run()
    )

    print(
        "Evaluation readiness:",
        evaluation[
            "readiness"
        ][
            "status"
        ],
    )

    print()
    print(
        "[7] Building reproducibility "
        "manifest..."
    )

    manifest = (
        build_manifest()
    )

    print(
        "Git commit:",
        manifest[
            "repository"
        ][
            "commit"
        ],
    )

    print()
    print(
        "[8] Validating release..."
    )

    result = (
        validate_release(
            strict_evaluation=(
                args
                .strict_evaluation
            )
        )
    )

    print()
    print(
        "FINAL STATUS:",
        result[
            "status"
        ],
    )

    print(
        "=" * 84
    )

    if result[
        "errors"
    ]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()