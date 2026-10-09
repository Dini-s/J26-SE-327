import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

DATA_ROOT = (
    PROJECT_ROOT
    / "data"
    / "component3"
)

RVUS_PATH = (
    DATA_ROOT
    / "processed"
    / "rvus"
    / "rvus.json"
)

PROFILES_PATH = (
    DATA_ROOT
    / "processed"
    / "evidence_profiles"
    / "evidence_profiles.json"
)

EVIDENCE_PATH = (
    DATA_ROOT
    / "processed"
    / "normalized_evidence"
    / "evidence.json"
)


def load(
    path: Path,
):
    if not path.exists():
        raise FileNotFoundError(
            path
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def main() -> None:
    rvus = load(
        RVUS_PATH
    )

    profiles = load(
        PROFILES_PATH
    )

    evidence = load(
        EVIDENCE_PATH
    )

    errors: list[str] = []

    rvu_ids = {
        item["rvu_id"]
        for item in rvus
    }

    profile_rvu_ids = {
        item["rvu_id"]
        for item in profiles
    }

    if (
        rvu_ids
        != profile_rvu_ids
    ):
        missing = sorted(
            rvu_ids
            - profile_rvu_ids
        )

        extra = sorted(
            profile_rvu_ids
            - rvu_ids
        )

        if missing:
            errors.append(
                "RVUs missing "
                f"ExpectedEvidenceProfile: "
                f"{missing}"
            )

        if extra:
            errors.append(
                "Profiles reference "
                f"unknown RVUs: "
                f"{extra}"
            )

    for rvu in rvus:
        for field in (
            "rvu_id",
            "requirement_id",
            "ac_id",
            "atomic_text",
            "source_text",
            "source_fragment",
            "source_span",
            "confidence",
            "extraction_method",
        ):
            if field not in rvu:
                errors.append(
                    f"{rvu.get('rvu_id')}: "
                    f"missing RVU field "
                    f"{field}"
                )

    for item in evidence:
        for field in (
            "evidence_id",
            "evidence_type",
            "title",
            "source_path",
            "source_tool",
        ):
            if not item.get(
                field
            ):
                errors.append(
                    f"{item.get('evidence_id')}: "
                    f"missing evidence "
                    f"provenance field "
                    f"{field}"
                )

    evidence_type_counts = (
        Counter(
            item["evidence_type"]
            for item
            in evidence
        )
    )

    automated = [
        item
        for item in evidence
        if (
            item["evidence_type"]
            == "AUTOMATED_TEST"
        )
    ]

    mapped = [
        item
        for item in automated
        if (
            item.get(
                "execution_status"
            )
            is not None
        )
    ]

    unresolved = [
        item
        for item in automated
        if (
            item.get(
                "execution_status"
            )
            is None
        )
    ]

    execution_statuses = Counter(
        item.get(
            "execution_status"
        )
        for item
        in automated
    )

    if len(mapped) < 75:
        errors.append(
            f"Only {len(mapped)} automated "
            f"tests mapped to execution results; "
            f"expected at least 75 for the "
            f"pinned PetClinic corpus."
        )

    if (
        evidence_type_counts.get(
            "MANUAL_TEST",
            0,
        )
        < 20
    ):
        errors.append(
            "Fewer than 20 manual "
            "evidence records were normalized."
        )

    if (
        evidence_type_counts.get(
            "PERFORMANCE_EVIDENCE",
            0,
        )
        < 6
    ):
        errors.append(
            "Fewer than 6 performance "
            "evidence records were normalized."
        )

    print()
    print("=" * 68)

    print(
        "ASPIRE C3 OUTPUT VALIDATION"
    )

    print("=" * 68)

    print(
        f"RVUs                  : "
        f"{len(rvus)}"
    )

    print(
        f"Evidence Profiles     : "
        f"{len(profiles)}"
    )

    print(
        f"Normalized Evidence   : "
        f"{len(evidence)}"
    )

    print(
        f"Automated Tests       : "
        f"{len(automated)}"
    )

    print(
        f"Execution Mapped      : "
        f"{len(mapped)}"
    )

    print(
        f"Execution Unresolved  : "
        f"{len(unresolved)}"
    )

    print(
        f"Manual Evidence       : "
        f"{evidence_type_counts.get('MANUAL_TEST', 0)}"
    )

    print(
        f"Performance Evidence  : "
        f"{evidence_type_counts.get('PERFORMANCE_EVIDENCE', 0)}"
    )

    print(
        f"Execution Statuses    : "
        f"{dict(execution_statuses)}"
    )

    if unresolved:
        print()

        print(
            "Automated source tests "
            "without a matching Surefire result:"
        )

        for item in unresolved:
            print(
                f"- "
                f"{item.get('class_name')}"
                f"#{item.get('method_name')}"
            )

    if errors:
        print()
        print(
            "VALIDATION FAILED"
        )

        for error in errors:
            print(
                f"- {error}"
            )

        raise SystemExit(
            1
        )

    print()

    print(
        "VALIDATION PASSED"
    )

    print(
        "RVU/profile linkage, provenance "
        "and execution mapping checks passed."
    )

    print("=" * 68)


if __name__ == "__main__":
    main()