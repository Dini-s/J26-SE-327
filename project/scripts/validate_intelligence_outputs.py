from agents.quality_agent import config
from agents.quality_agent.services.dataset_service import (
    DatasetService,
)


REQUIRED_FILES = [
    config.ADEQUACY_ASSESSMENTS_PATH,
    config.RVU_ADEQUACY_PATH,
    config.RVU_VALIDATION_PATH,
    config.REQUIREMENT_INTELLIGENCE_PATH,
    config.GAPS_PATH,
    config.RECOMMENDATIONS_PATH,
    config.ANALYTICS_PATH,
]


def main() -> None:
    errors = []

    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(
                f"Missing output: {path}"
            )

    if errors:
        for error in errors:
            print(error)

        raise SystemExit(1)

    rvus = DatasetService.load_json(
        config.RVUS_PATH
    )

    summaries = DatasetService.load_json(
        config.RVU_ADEQUACY_PATH
    )

    validations = DatasetService.load_json(
        config.RVU_VALIDATION_PATH
    )

    intelligence = DatasetService.load_json(
        config
        .REQUIREMENT_INTELLIGENCE_PATH
    )

    analytics = DatasetService.load_json(
        config.ANALYTICS_PATH
    )

    print()
    print("=" * 72)
    print(
        "C3 INTELLIGENCE OUTPUT VALIDATION"
    )
    print("=" * 72)

    print(
        "RVUs                    :",
        len(rvus),
    )

    print(
        "RVU Adequacy Summaries  :",
        len(summaries),
    )

    print(
        "RVU Validation Results  :",
        len(validations),
    )

    print(
        "Requirement Intelligence:",
        len(intelligence),
    )

    if len(summaries) != len(rvus):
        errors.append(
            "Adequacy summary count "
            "does not match RVU count."
        )

    if len(validations) != len(rvus):
        errors.append(
            "Validation result count "
            "does not match RVU count."
        )

    if len(intelligence) != 30:
        errors.append(
            "Expected intelligence for "
            "30 requirements."
        )

    if (
        "overview"
        not in analytics
    ):
        errors.append(
            "Analytics overview missing."
        )

    if (
        "requirements"
        not in analytics
    ):
        errors.append(
            "Analytics requirements missing."
        )

    if errors:
        print()
        print("VALIDATION FAILED")

        for error in errors:
            print(" -", error)

        raise SystemExit(1)

    print()
    print("VALIDATION PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()