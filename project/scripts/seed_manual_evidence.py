import json
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "component3"
    / "raw"
    / "manual_tests"
    / "manual_tests.json"
)


def case(
    evidence_id: str,
    title: str,
    description: str,
    preconditions: list[str],
    inputs: list[str],
    steps: list[str],
    expected_result: str,
    *,
    synthetic: bool = False,
    source_tool: str = (
        "C3_MANUAL_CURATED"
    ),
) -> dict:

    return {
        "evidence_id":
        evidence_id,

        "title":
        title,

        "description":
        description,

        "preconditions":
        preconditions,

        "inputs":
        inputs,

        "steps":
        steps,

        "expected_result":
        expected_result,

        "execution_status":
        "NOT_EXECUTED",

        "source_tool":
        source_tool,

        "source_version":
        "1.0",

        "synthetic":
        synthetic,
    }


MANUAL_TESTS = [
    case(
        "MT-001",
        "Search owner using an existing last name",
        "Positive owner-search scenario.",
        [
            "A registered owner exists."
        ],
        [
            "Existing owner last name"
        ],
        [
            "Open owner search.",
            "Enter an existing last name.",
            "Submit the search."
        ],
        (
            "Matching owner records "
            "are displayed."
        ),
    ),

    case(
        "MT-002",
        "Search owner with no matching record",
        "Negative owner-search scenario.",
        [
            "The application is available."
        ],
        [
            "Unknown owner last name"
        ],
        [
            "Open owner search.",
            "Enter a non-existing last name.",
            "Submit the search."
        ],
        (
            "A no-match outcome is displayed "
            "and no unrelated owner is returned."
        ),
    ),

    case(
        "MT-003",
        "Register owner using valid information",
        "Positive owner-registration scenario.",
        [
            "Owner creation workflow is available."
        ],
        [
            "Valid first name",
            "Valid last name",
            "Valid address",
            "Valid city",
            "Valid telephone"
        ],
        [
            "Open the new owner form.",
            "Enter valid owner details.",
            "Submit the form."
        ],
        (
            "A persistent owner record is "
            "created and can be opened afterwards."
        ),
    ),

    case(
        "MT-004",
        "Reject owner registration with missing mandatory information",
        "Negative owner-validation scenario.",
        [
            "Owner creation workflow is available."
        ],
        [
            "Owner submission missing a mandatory field"
        ],
        [
            "Open the new owner form.",
            "Leave a mandatory field empty.",
            "Submit the form."
        ],
        (
            "Registration is rejected and "
            "validation feedback is displayed."
        ),
    ),

    case(
        "MT-005",
        "Update existing owner information",
        "Owner-update scenario.",
        [
            "An owner already exists."
        ],
        [
            "Valid updated owner information"
        ],
        [
            "Open owner details.",
            "Edit the owner.",
            "Save valid changes."
        ],
        (
            "Updated values are persisted while "
            "the owner identity remains unchanged."
        ),
    ),

    case(
        "MT-006",
        "View owner details with associated pets",
        "Owner-details read scenario.",
        [
            "An owner with a registered pet exists."
        ],
        [
            "Existing owner"
        ],
        [
            "Open the owner details page."
        ],
        (
            "Owner information and associated "
            "pet information are displayed."
        ),
    ),

    case(
        "MT-007",
        "Register pet under an existing owner",
        "Positive pet-registration scenario.",
        [
            "A valid owner exists."
        ],
        [
            "Valid pet name",
            "Valid birth date",
            "Valid pet type"
        ],
        [
            "Open owner details.",
            "Choose add pet.",
            "Enter valid pet information.",
            "Submit."
        ],
        (
            "The pet is created and remains "
            "associated with the selected owner."
        ),
    ),

    case(
        "MT-008",
        "Reject invalid pet registration",
        "Negative pet-validation scenario.",
        [
            "A valid owner exists."
        ],
        [
            "Pet submission missing mandatory information"
        ],
        [
            "Open add-pet workflow.",
            "Omit mandatory information.",
            "Submit."
        ],
        (
            "Pet creation is rejected and "
            "validation feedback is displayed."
        ),
    ),

    case(
        "MT-009",
        "Update existing pet information",
        "Pet-update scenario.",
        [
            "An owner and pet exist."
        ],
        [
            "Valid updated pet information"
        ],
        [
            "Open pet details.",
            "Edit the pet.",
            "Save the changes."
        ],
        (
            "Pet information is updated while "
            "the owner association is preserved."
        ),
    ),

    case(
        "MT-010",
        "Register valid veterinary visit",
        "Positive visit-creation scenario.",
        [
            "An existing pet is available."
        ],
        [
            "Valid visit date",
            "Valid visit description"
        ],
        [
            "Open pet details.",
            "Choose add visit.",
            "Enter valid visit information.",
            "Submit."
        ],
        (
            "The visit is created and becomes "
            "visible in the pet visit history."
        ),
    ),

    case(
        "MT-011",
        "Reject invalid veterinary visit",
        "Negative visit-validation scenario.",
        [
            "An existing pet is available."
        ],
        [
            "Visit submission missing mandatory information"
        ],
        [
            "Open add-visit workflow.",
            "Omit mandatory information.",
            "Submit."
        ],
        (
            "Visit creation is rejected and "
            "validation feedback is displayed."
        ),
    ),

    case(
        "MT-012",
        "Display veterinarian listing and specialties",
        "Veterinarian read scenario.",
        [
            "Veterinarian records exist."
        ],
        [],
        [
            "Open the veterinarian listing."
        ],
        (
            "Veterinarian records are displayed "
            "and specialty information is shown "
            "when available."
        ),
    ),

    case(
        "MT-013",
        "Lock account on fifth failed authentication attempt",
        "Controlled security boundary scenario.",
        [
            (
                "Account is active and the "
                "failed-attempt counter is zero."
            )
        ],
        [
            (
                "Five consecutive invalid "
                "authentication attempts"
            )
        ],
        [
            (
                "Submit invalid credentials "
                "five consecutive times."
            )
        ],
        (
            "The account becomes locked after "
            "the fifth failed attempt."
        ),
    ),

    case(
        "MT-014",
        "Reject authentication while account is locked",
        "Controlled locked-state scenario.",
        [
            "Account is currently locked."
        ],
        [
            "Valid credentials"
        ],
        [
            (
                "Attempt authentication while "
                "the account remains locked."
            )
        ],
        (
            "Authentication is rejected until "
            "the lock condition expires or "
            "is cleared."
        ),
    ),

    case(
        "MT-015",
        "Reject expired password-reset token",
        "Controlled token-expiry scenario.",
        [
            (
                "A reset token was issued "
                "more than 30 minutes ago."
            )
        ],
        [
            "Expired reset token"
        ],
        [
            (
                "Attempt password reset using "
                "the expired token."
            )
        ],
        (
            "The reset request is rejected."
        ),
    ),

    case(
        "MT-016",
        "Reject reused password-reset token",
        "Controlled single-use-token scenario.",
        [
            (
                "A reset token has already "
                "been consumed."
            )
        ],
        [
            "Previously consumed reset token"
        ],
        [
            (
                "Attempt another reset using "
                "the same token."
            )
        ],
        (
            "Token reuse is rejected."
        ),
    ),

    case(
        "MT-017",
        "Deny administrative action for non-administrator",
        "Controlled authorization-negative scenario.",
        [
            (
                "User is authenticated without "
                "administrator privileges."
            )
        ],
        [
            "Administrative account action"
        ],
        [
            "Attempt the administrative action."
        ],
        (
            "Access is denied and the target "
            "account remains unchanged."
        ),
    ),

    case(
        "MT-018",
        "Allow administrative action for administrator",
        "Controlled authorization-positive scenario.",
        [
            (
                "User is authenticated as "
                "an administrator."
            )
        ],
        [
            "Administrative account action"
        ],
        [
            "Perform the administrative action."
        ],
        (
            "The authorized administrative "
            "action succeeds."
        ),
    ),

    case(
        "MT-019",
        "Accept allowed file exactly at 5 MB",
        "Controlled upload boundary scenario.",
        [
            "Upload functionality is available."
        ],
        [
            "Allowed file type exactly 5 MB"
        ],
        [
            "Upload the file."
        ],
        (
            "The file is accepted."
        ),
    ),

    case(
        "MT-020",
        "Reject file larger than 5 MB",
        "Controlled upload negative-boundary scenario.",
        [
            "Upload functionality is available."
        ],
        [
            "Allowed file type larger than 5 MB"
        ],
        [
            "Upload the file."
        ],
        (
            "The file is rejected."
        ),
    ),

    case(
        "MT-021",
        "Owner page looks correct",
        (
            "Deliberately weak evidence fixture "
            "for later adequacy evaluation."
        ),
        [],
        [],
        [
            "Open an owner page."
        ],
        (
            "The page looks correct."
        ),
        synthetic=True,
        source_tool=(
            "C3_CONTROLLED_WEAK_EVIDENCE"
        ),
    ),

    case(
        "MT-022",
        "Change application theme",
        (
            "Deliberately irrelevant evidence "
            "fixture for retrieval evaluation."
        ),
        [],
        [
            "Theme selection"
        ],
        [
            "Change the application theme."
        ],
        (
            "The visual theme changes."
        ),
        synthetic=True,
        source_tool=(
            "C3_CONTROLLED_IRRELEVANT_EVIDENCE"
        ),
    ),
]


def main() -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            MANUAL_TESTS,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        "ASPIRE C3 Manual Evidence Dataset"
    )
    print("=" * 50)

    print(
        f"Evidence records: "
        f"{len(MANUAL_TESTS)}"
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )

    print(
        "Execution status: NOT_EXECUTED "
        "(no manual PASS results are fabricated)"
    )

    print("=" * 50)


if __name__ == "__main__":
    main()