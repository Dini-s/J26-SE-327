from agents.quality_agent.schemas import (
    AcceptanceCriterion,
    RequirementRecord,
)

from agents.quality_agent.services.evidence_profile import (
    EvidenceProfileGenerator,
)

from agents.quality_agent.services.rvu_extractor import (
    RVUExtractor,
)


def test_functional_profile_supported():

    requirement = RequirementRecord(
        requirement_id="REQ-F-001",

        title=(
            "Reject Invalid Input"
        ),

        text=(
            "Reject invalid input."
        ),

        type="FUNCTIONAL",

        subtype="VALIDATION",

        risk="HIGH",

        source="TEST_FIXTURE",

        acceptance_criteria=[
            AcceptanceCriterion(
                ac_id="AC-F-001",

                text=(
                    "The system shall reject "
                    "invalid input."
                ),
            )
        ],
    )

    rvus = (
        RVUExtractor()
        .extract(
            [requirement]
        )
    )

    profile = (
        EvidenceProfileGenerator()
        .generate(
            [requirement],
            rvus,
        )[0]
    )

    assert (
        profile.support_status
        == "SUPPORTED"
    )


def test_performance_profile_fields():

    requirement = RequirementRecord(
        requirement_id=(
            "REQ-NFR-001"
        ),

        title=(
            "API Performance"
        ),

        text=(
            "API performance."
        ),

        type=(
            "NON_FUNCTIONAL"
        ),

        subtype=(
            "PERFORMANCE"
        ),

        risk="HIGH",

        source=(
            "TEST_FIXTURE"
        ),

        acceptance_criteria=[
            AcceptanceCriterion(
                ac_id=(
                    "AC-NFR-001"
                ),

                text=(
                    "The API shall maintain a "
                    "p95 response time below "
                    "2 seconds with 100 concurrent "
                    "users for 10 minutes."
                ),
            )
        ],
    )

    rvus = (
        RVUExtractor()
        .extract(
            [requirement]
        )
    )

    profile = (
        EvidenceProfileGenerator()
        .generate(
            [requirement],
            rvus,
        )[0]
    )

    assert (
        profile.metric
        == "response_time"
    )

    assert (
        profile.percentile
        == "p95"
    )

    assert (
        profile.operator
        == "<"
    )

    assert (
        profile.threshold
        == 2.0
    )

    assert (
        profile.load
        == 100
    )

    assert (
        profile.duration_seconds
        == 600
    )


def test_unsupported_nfr_not_falsely_supported():

    requirement = RequirementRecord(
        requirement_id=(
            "REQ-NFR-002"
        ),

        title="Accessibility",

        text=(
            "Accessibility requirement."
        ),

        type=(
            "NON_FUNCTIONAL"
        ),

        subtype=(
            "ACCESSIBILITY"
        ),

        risk="MEDIUM",

        source=(
            "TEST_FIXTURE"
        ),

        acceptance_criteria=[
            AcceptanceCriterion(
                ac_id=(
                    "AC-NFR-002"
                ),

                text=(
                    "The application shall "
                    "support keyboard navigation."
                ),
            )
        ],
    )

    rvus = (
        RVUExtractor()
        .extract(
            [requirement]
        )
    )

    profile = (
        EvidenceProfileGenerator()
        .generate(
            [requirement],
            rvus,
        )[0]
    )

    assert (
        profile.support_status
        == "UNSUPPORTED"
    )