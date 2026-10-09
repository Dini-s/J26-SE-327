import sys
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if (
    str(PROJECT_ROOT)
    not in sys.path
):
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from agents.quality_agent.agent import (
    QualityAgent,
)


def main() -> None:
    agent = QualityAgent()

    print()
    print("=" * 72)

    print(
        "ASPIRE QUALITY & TESTING "
        "INTELLIGENCE PIPELINE"
    )

    print("=" * 72)

    processed = (
        agent.process_requirements()
    )

    print(
        f"Requirements      : "
        f"{len(processed['requirements'])}"
    )

    print(
        f"RVUs              : "
        f"{len(processed['rvus'])}"
    )

    print(
        f"Evidence Profiles : "
        f"{len(processed['profiles'])}"
    )

    evidence = (
        agent.normalize_evidence()
    )

    print(
        f"Evidence Items    : "
        f"{len(evidence)}"
    )

    print(
        "Automated Tests   :",
        sum(
            1
            for item in evidence
            if (
                item.evidence_type
                == "AUTOMATED_TEST"
            )
        ),
    )

    print(
        "Execution Mapped  :",
        sum(
            1
            for item in evidence
            if (
                item.evidence_type
                == "AUTOMATED_TEST"
                and item.execution_status
                is not None
            )
        ),
    )

    print(
        "Manual Evidence   :",
        sum(
            1
            for item in evidence
            if (
                item.evidence_type
                == "MANUAL_TEST"
            )
        ),
    )

    print(
        "Performance       :",
        sum(
            1
            for item in evidence
            if (
                item.evidence_type
                == "PERFORMANCE_EVIDENCE"
            )
        ),
    )

    selected_rvu = (
        processed["rvus"][0]
    )

    print()

    print(
        f"Retrieval demo RVU: "
        f"{selected_rvu.rvu_id}"
    )

    print(
        selected_rvu.atomic_text
    )

    for method in (
        "keyword",
        "tfidf",
        "semantic",
    ):
        print()

        print(
            f"--- "
            f"{method.upper()} "
            f"TOP 5 ---"
        )

        matches = agent.retrieve(
            selected_rvu.rvu_id,
            method,
            5,
        )

        for match in matches:
            print(
                f"{match.rank}. "
                f"{match.evidence_id} | "
                f"{match.similarity_score:.4f} | "
                f"{match.evidence_title}"
            )

    print()
    print("=" * 72)

    print(
        "PIPELINE COMPLETED SUCCESSFULLY"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()