import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    PROJECT_ROOT
    / "data"
    / "component3"
    / "raw"
    / "requirements"
    / "requirements.json"
)


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Requirements dataset not found: {DATASET_PATH}"
        )

    with DATASET_PATH.open("r", encoding="utf-8") as file:
        requirements = json.load(file)

    errors: list[str] = []

    requirement_ids: set[str] = set()
    acceptance_criterion_ids: set[str] = set()

    type_counter = Counter()
    subtype_counter = Counter()
    source_counter = Counter()
    risk_counter = Counter()

    ac_count = 0

    required_fields = {
        "requirement_id",
        "title",
        "text",
        "type",
        "subtype",
        "risk",
        "version",
        "source",
        "acceptance_criteria",
    }

    for requirement in requirements:
        requirement_id = requirement.get("requirement_id")

        if not requirement_id:
            errors.append("Requirement without requirement_id detected.")
            continue

        if requirement_id in requirement_ids:
            errors.append(
                f"Duplicate requirement ID: {requirement_id}"
            )

        requirement_ids.add(requirement_id)

        missing = required_fields - requirement.keys()

        if missing:
            errors.append(
                f"{requirement_id}: missing fields: "
                f"{', '.join(sorted(missing))}"
            )

        req_type = requirement.get("type", "UNKNOWN")
        subtype = requirement.get("subtype", "UNKNOWN")
        source = requirement.get("source", "UNKNOWN")
        risk = requirement.get("risk", "UNKNOWN")

        type_counter[req_type] += 1
        subtype_counter[subtype] += 1
        source_counter[source] += 1
        risk_counter[risk] += 1

        criteria = requirement.get(
            "acceptance_criteria",
            [],
        )

        if not criteria:
            errors.append(
                f"{requirement_id}: has no acceptance criteria."
            )

        for criterion in criteria:
            ac_count += 1

            ac_id = criterion.get("ac_id")
            text = criterion.get("text")

            if not ac_id:
                errors.append(
                    f"{requirement_id}: AC without ac_id."
                )
                continue

            if ac_id in acceptance_criterion_ids:
                errors.append(
                    f"Duplicate acceptance criterion ID: {ac_id}"
                )

            acceptance_criterion_ids.add(ac_id)

            if not text or not text.strip():
                errors.append(
                    f"{ac_id}: empty acceptance criterion text."
                )

    print()
    print("=" * 68)
    print("ASPIRE C3 REQUIREMENTS DATASET VALIDATION")
    print("=" * 68)

    print(f"Dataset: {DATASET_PATH}")
    print()

    print(f"Total Requirements       : {len(requirements)}")
    print(f"Acceptance Criteria      : {ac_count}")
    print(f"Unique Requirement IDs  : {len(requirement_ids)}")
    print(f"Unique AC IDs           : {len(acceptance_criterion_ids)}")

    print()
    print("Requirement Types")
    print("-" * 35)

    for key, value in sorted(type_counter.items()):
        print(f"{key:<25} {value}")

    print()
    print("Sources")
    print("-" * 35)

    for key, value in sorted(source_counter.items()):
        print(f"{key:<25} {value}")

    print()
    print("Risks")
    print("-" * 35)

    for key, value in sorted(risk_counter.items()):
        print(f"{key:<25} {value}")

    print()
    print("Subtypes")
    print("-" * 35)

    for key, value in sorted(subtype_counter.items()):
        print(f"{key:<25} {value}")

    print()

    if errors:
        print("VALIDATION FAILED")
        print("-" * 68)

        for error in errors:
            print(f"- {error}")

        raise SystemExit(1)

    print("VALIDATION PASSED")
    print(
        "No duplicate IDs, missing fields, "
        "or empty acceptance criteria detected."
    )
    print("=" * 68)


if __name__ == "__main__":
    main()