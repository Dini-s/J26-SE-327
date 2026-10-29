from agents.quality_agent.schemas import (
    AcceptanceCriterion,
    RequirementRecord,
)

from agents.quality_agent.services.rvu_extractor import (
    RVUExtractor,
)


def make_requirement(
    criterion_text: str,
) -> RequirementRecord:

    return RequirementRecord(
        requirement_id=(
            "REQ-TEST-001"
        ),

        title=(
            "Test Requirement"
        ),

        text=(
            "Test requirement."
        ),

        type="FUNCTIONAL",

        subtype=(
            "SECURITY_BEHAVIOR"
        ),

        risk="HIGH",

        version=1,

        source=(
            "TEST_FIXTURE"
        ),

        acceptance_criteria=[
            AcceptanceCriterion(
                ac_id=(
                    "AC-TEST-001"
                ),
                text=(
                    criterion_text
                ),
            )
        ],
    )


def test_atomic_ac_produces_one_rvu():
    result = (
        RVUExtractor()
        .extract(
            [
                make_requirement(
                    "The system shall reject "
                    "an invalid token."
                )
            ]
        )
    )

    assert len(result) == 1


def test_compound_ac_produces_two_rvus():
    result = (
        RVUExtractor()
        .extract(
            [
                make_requirement(
                    "The account shall become "
                    "locked after five failed "
                    "authentication attempts and "
                    "remain locked for 30 minutes."
                )
            ]
        )
    )

    assert len(result) == 2

    assert (
        "become locked"
        in result[0]
        .atomic_text
        .lower()
    )

    assert (
        "remain locked"
        in result[1]
        .atomic_text
        .lower()
    )


def test_rvu_preserves_provenance():
    source = (
        "The system shall reject "
        "an invalid token."
    )

    result = (
        RVUExtractor()
        .extract(
            [
                make_requirement(
                    source
                )
            ]
        )
    )

    assert (
        result[0].source_text
        == source
    )

    assert (
        result[0].source_fragment
    )

    assert (
        result[0].ac_id
        == "AC-TEST-001"
    )