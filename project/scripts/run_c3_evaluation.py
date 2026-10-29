from __future__ import annotations

import argparse

from agents.quality_agent import (
    config,
)

from agents.quality_agent.agent import (
    QualityAgent,
)

from agents.quality_agent.services.evaluation import (
    EvaluationService,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Return a non-zero exit code "
            "when required gold-label "
            "sections are incomplete."
        ),
    )

    args = parser.parse_args()

    agent = QualityAgent()

    if not (
        config.RVUS_PATH.exists()
    ):
        agent.process_requirements()

    if not (
        config
        .NORMALIZED_EVIDENCE_PATH
        .exists()
    ):
        agent.normalize_evidence()

    if not (
        config
        .REQUIREMENT_INTELLIGENCE_PATH
        .exists()
    ):
        agent.analyze_quality()

    if not (
        config
        .REVALIDATION_RESULTS_PATH
        .exists()
    ):
        agent.run_revalidation()

    service = EvaluationService(
        agent=agent
    )

    results = service.run()

    readiness = results[
        "readiness"
    ]

    print()
    print(
        "=" * 76
    )

    print(
        "ASPIRE COMPONENT 3 "
        "EMPIRICAL EVALUATION"
    )

    print(
        "=" * 76
    )

    print(
        "Gold-label readiness :",
        readiness[
            "status"
        ],
    )

    print(
        "Missing sections     :",
        (
            ", ".join(
                readiness[
                    "missing_sections"
                ]
            )
            or "None"
        ),
    )

    retrieval = results[
        "retrieval"
    ]

    if (
        retrieval.get(
            "status"
        )
        == "EVALUATED"
    ):
        for method, metrics in (
            retrieval[
                "methods"
            ].items()
        ):
            print()
            print(
                method.upper()
            )

            print(
                "  Precision@K :",
                metrics[
                    "precision_at_k"
                ],
            )

            print(
                "  Recall@K    :",
                metrics[
                    "recall_at_k"
                ],
            )

            print(
                "  F1@K        :",
                metrics[
                    "f1_at_k"
                ],
            )

            print(
                "  MRR         :",
                metrics[
                    "mrr"
                ],
            )

            print(
                "  p95 latency :",
                (
                    f"{metrics['latency_p95_ms']}"
                    " ms"
                ),
            )

    adequacy = results[
        "adequacy"
    ]

    if (
        adequacy.get(
            "status"
        )
        == "EVALUATED"
    ):
        print()
        print(
            "Adequacy Macro-F1     :",
            adequacy[
                "macro_f1"
            ],
        )

        print(
            "False-Adequate Rate   :",
            adequacy[
                "false_adequate_rate"
            ],
        )

    rvc = results[
        "rvc"
    ]

    if (
        rvc.get(
            "status"
        )
        == "EVALUATED"
    ):
        print()
        print(
            "RVC MAE               :",
            rvc["mae"],
        )

        print(
            "RVC Spearman          :",
            rvc[
                "spearman_correlation"
            ],
        )

    revalidation = results[
        "revalidation"
    ]

    if (
        revalidation.get(
            "status"
        )
        == "EVALUATED"
    ):
        print()
        print(
            "Revalidation Accuracy :",
            revalidation[
                "accuracy"
            ],
        )

        print(
            "Revalidation Macro-F1 :",
            revalidation[
                "macro_f1"
            ],
        )

    print()
    print(
        "Output:",
        config
        .EVALUATION_RESULTS_PATH,
    )

    print(
        "=" * 76
    )

    if (
        args.strict
        and
        readiness[
            "status"
        ]
        != "READY"
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()