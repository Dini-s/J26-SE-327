from agents.quality_agent.agent import (
    QualityAgent,
)


def main() -> None:
    reports = (
        QualityAgent()
        .run_revalidation()
    )

    print()
    print(
        "=" * 84
    )

    print(
        "ASPIRE C3 TARGETED REVALIDATION"
    )

    print(
        "=" * 84
    )

    print(
        "Change Cases             :",
        len(reports),
    )

    print(
        "Functional Cases         :",
        sum(
            1
            for report
            in reports
            if (
                report
                .requirement_type
                == "FUNCTIONAL"
            )
        ),
    )

    print(
        "Non-Functional Cases     :",
        sum(
            1
            for report
            in reports
            if (
                report
                .requirement_type
                == "NON_FUNCTIONAL"
            )
        ),
    )

    print(
        "=" * 84
    )

    for report in reports:
        print()

        print(
            f"{report.change_id} "
            f"| "
            f"{report.requirement_id}"
        )

        print(
            "Type                     :",
            (
                f"{report.requirement_type}"
                f" / "
                f"{report.requirement_subtype}"
            ),
        )

        print(
            "Affected RVUs            :",
            ", ".join(
                report
                .affected_rvu_ids
            ),
        )

        print(
            "Reusable                 :",
            report.reusable_count,
        )

        print(
            "Modification Required    :",
            report
            .modification_required_count,
        )

        print(
            "Outdated                 :",
            report.outdated_count,
        )

        print(
            "New Evidence Required    :",
            report
            .new_evidence_required_count,
        )

        print(
            "-" * 84
        )

        for decision in (
            report.decisions
        ):
            print(
                f"{decision.evidence_name:<46}"
                f"{decision.classification}"
            )

        print(
            "-" * 84
        )

    total_reusable = sum(
        item.reusable_count
        for item
        in reports
    )

    total_modify = sum(
        item
        .modification_required_count
        for item
        in reports
    )

    total_outdated = sum(
        item.outdated_count
        for item
        in reports
    )

    total_new = sum(
        item
        .new_evidence_required_count
        for item
        in reports
    )

    print()
    print(
        "=" * 84
    )

    print(
        "GLOBAL REVALIDATION SUMMARY"
    )

    print(
        "=" * 84
    )

    print(
        "Reusable                 :",
        total_reusable,
    )

    print(
        "Modification Required    :",
        total_modify,
    )

    print(
        "Outdated                 :",
        total_outdated,
    )

    print(
        "New Evidence Required    :",
        total_new,
    )

    print(
        "=" * 84
    )


if __name__ == "__main__":
    main()