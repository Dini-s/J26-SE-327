import sys
from collections import Counter
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
    result = (
        QualityAgent()
        .process_requirements()
    )

    support = Counter(
        profile.support_status
        for profile
        in result[
            "profiles"
        ]
    )

    review_required = sum(
        1
        for rvu
        in result["rvus"]
        if rvu.requires_review
    )

    print()
    print("=" * 68)

    print(
        "ASPIRE C3 REQUIREMENT PROCESSING"
    )

    print("=" * 68)

    print(
        f"Requirements            : "
        f"{len(result['requirements'])}"
    )

    print(
        f"RVUs                    : "
        f"{len(result['rvus'])}"
    )

    print(
        f"Expected Profiles       : "
        f"{len(result['profiles'])}"
    )

    print(
        f"Supported Profiles      : "
        f"{support.get('SUPPORTED', 0)}"
    )

    print(
        f"Review Required         : "
        f"{support.get('REVIEW_REQUIRED', 0)}"
    )

    print(
        f"Unsupported Profiles    : "
        f"{support.get('UNSUPPORTED', 0)}"
    )

    print(
        f"RVUs Requiring Review   : "
        f"{review_required}"
    )

    print("=" * 68)


if __name__ == "__main__":
    main()