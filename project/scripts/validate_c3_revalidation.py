from pydantic import (
    TypeAdapter,
)

from agents.quality_agent import (
    config,
)

from agents.quality_agent.schemas import (
    RevalidationChangeCase,
    RevalidationReport,
)

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)


EXPECTED_CLASSES = {
    "REUSABLE",
    "MODIFICATION_REQUIRED",
    "OUTDATED",
    "NEW_EVIDENCE_REQUIRED",
}


def main() -> None:
    raw_cases = (
        DatasetService
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
        raw_cases
    )

    if not (
        config
        .REVALIDATION_RESULTS_PATH
        .exists()
    ):
        raise RuntimeError(
            "Revalidation output is missing. "
            "Run scripts/run_c3_revalidation.py first."
        )

    raw_reports = (
        DatasetService
        .load_json(
            config
            .REVALIDATION_RESULTS_PATH
        )
    )

    reports = TypeAdapter(
        list[
            RevalidationReport
        ]
    ).validate_python(
        raw_reports
    )

    requirements = (
        DatasetService
        .load_requirements(
            config
            .REQUIREMENTS_PATH
        )
    )

    requirement_map = {
        item.requirement_id:
        item

        for item
        in requirements
    }

    rvus = (
        DatasetService
        .load_json(
            config.RVUS_PATH
        )
    )

    rvu_map = {
        item["rvu_id"]:
        item

        for item
        in rvus
    }

    errors: list[str] = []

    change_ids = [
        case.change_id
        for case
        in cases
    ]

    if (
        len(change_ids)
        != len(
            set(change_ids)
        )
    ):
        errors.append(
            "Duplicate change IDs detected."
        )

    if len(cases) < 6:
        errors.append(
            "Expected at least six controlled "
            "revalidation cases."
        )

    functional_count = sum(
        1
        for case
        in cases
        if (
            case.requirement_type
            == "FUNCTIONAL"
        )
    )

    non_functional_count = sum(
        1
        for case
        in cases
        if (
            case.requirement_type
            == "NON_FUNCTIONAL"
        )
    )

    if functional_count < 3:
        errors.append(
            "Expected at least three "
            "functional change cases."
        )

    if non_functional_count < 3:
        errors.append(
            "Expected at least three "
            "non-functional change cases."
        )

    for case in cases:
        requirement = (
            requirement_map.get(
                case.requirement_id
            )
        )

        if requirement is None:
            errors.append(
                (
                    f"{case.change_id}: "
                    f"unknown requirement "
                    f"{case.requirement_id}"
                )
            )

            continue

        if (
            requirement.type
            != case.requirement_type
        ):
            errors.append(
                (
                    f"{case.change_id}: "
                    f"requirement type mismatch."
                )
            )

        if (
            requirement.subtype
            != case
            .requirement_subtype
        ):
            errors.append(
                (
                    f"{case.change_id}: "
                    f"requirement subtype mismatch."
                )
            )

        for rvu_id in (
            case.affected_rvu_ids
        ):
            rvu = (
                rvu_map.get(
                    rvu_id
                )
            )

            if rvu is None:
                errors.append(
                    (
                        f"{case.change_id}: "
                        f"unknown RVU "
                        f"{rvu_id}"
                    )
                )

                continue

            if (
                rvu[
                    "requirement_id"
                ]
                != case.requirement_id
            ):
                errors.append(
                    (
                        f"{case.change_id}: "
                        f"{rvu_id} belongs to "
                        f"a different requirement."
                    )
                )

    if (
        len(reports)
        != len(cases)
    ):
        errors.append(
            "Generated report count does not "
            "match input change-case count."
        )

    observed_classes = {
        decision.classification

        for report
        in reports

        for decision
        in report.decisions
    }

    missing_classes = (
        EXPECTED_CLASSES
        - observed_classes
    )

    if missing_classes:
        errors.append(
            (
                "Missing revalidation "
                "classification coverage: "
                + ", ".join(
                    sorted(
                        missing_classes
                    )
                )
            )
        )

    print()
    print(
        "=" * 72
    )

    print(
        "C3 REVALIDATION VALIDATION"
    )

    print(
        "=" * 72
    )

    print(
        "Change Cases         :",
        len(cases),
    )

    print(
        "Functional           :",
        functional_count,
    )

    print(
        "Non-Functional       :",
        non_functional_count,
    )

    print(
        "Generated Reports    :",
        len(reports),
    )

    print(
        "Decision Classes     :",
        ", ".join(
            sorted(
                observed_classes
            )
        ),
    )

    print(
        "Affected RVUs        :",
        sum(
            len(
                case
                .affected_rvu_ids
            )
            for case
            in cases
        ),
    )

    print(
        "=" * 72
    )

    if errors:
        print(
            "VALIDATION FAILED"
        )

        for error in errors:
            print(
                " -",
                error,
            )

        raise SystemExit(1)

    print(
        "VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()