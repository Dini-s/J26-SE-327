from agents.quality_agent.schemas import (
    ExpectedEvidenceProfile,
    RequirementValidationUnit,
    RVUAdequacySummary,
    SourceSpan,
    ValidationEvidence,
)

from agents.quality_agent.services.validation_service import (
    ValidationService,
)


def make_rvu():
    return RequirementValidationUnit(
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        ac_id="AC-X-01",
        atomic_text=(
            "The system shall reject "
            "invalid input."
        ),
        behavior_type="NEGATIVE",
        source_text=(
            "The system shall reject "
            "invalid input."
        ),
        source_fragment=(
            "The system shall reject "
            "invalid input."
        ),
        source_span=SourceSpan(
            start=0,
            end=38,
        ),
        constraints=[],
        confidence=1.0,
        extraction_method="TEST",
    )


def make_profile():
    return ExpectedEvidenceProfile(
        profile_id="PROFILE-X",
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        ac_id="AC-X-01",
        requirement_type="FUNCTIONAL",
        requirement_subtype="VALIDATION",
        evidence_type="FUNCTIONAL_TEST",
    )


def make_evidence(status="PASS"):
    return ValidationEvidence(
        evidence_id="EV-X",
        evidence_type="AUTOMATED_TEST",
        title="rejectInvalidInput",
        assertions=[
            "assert rejected"
        ],
        execution_status=status,
        source_path="test.java",
        source_tool="JUnit",
    )


def test_adequate_passed_evidence_validates_rvu():
    summary = RVUAdequacySummary(
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        support_status="SUPPORTED",
        evidence_found=True,
        adequacy_status="ADEQUATE",
        best_evidence_id="EV-X",
        best_relevance_score=0.9,
        best_adequacy_score=0.9,
        adequate_evidence_ids=[
            "EV-X"
        ],
        contributing_evidence_ids=[
            "EV-X"
        ],
    )

    result = (
        ValidationService()
        .evaluate_rvus(
            rvus=[make_rvu()],
            profiles=[make_profile()],
            summaries=[summary],
            evidence=[
                make_evidence("PASS")
            ],
        )[0]
    )

    assert (
        result.validation_status
        == "VALIDATED"
    )

    assert (
        result.execution_satisfied
        is True
    )


def test_adequate_failed_evidence_is_not_validated():
    summary = RVUAdequacySummary(
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        support_status="SUPPORTED",
        evidence_found=True,
        adequacy_status="ADEQUATE",
        best_evidence_id="EV-X",
        best_relevance_score=0.9,
        best_adequacy_score=0.9,
        adequate_evidence_ids=[
            "EV-X"
        ],
        contributing_evidence_ids=[
            "EV-X"
        ],
    )

    result = (
        ValidationService()
        .evaluate_rvus(
            rvus=[make_rvu()],
            profiles=[make_profile()],
            summaries=[summary],
            evidence=[
                make_evidence("FAIL")
            ],
        )[0]
    )

    assert (
        result.validation_status
        == "PARTIAL"
    )

    assert (
        result.execution_satisfied
        is False
    )