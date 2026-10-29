from agents.quality_agent.schemas import (
    ExpectedEvidenceProfile,
    RequirementValidationUnit,
    RVUAdequacySummary,
    SourceSpan,
    ValidationEvidence,
)

from agents.quality_agent.services.execution_provenance import (
    ExecutionProvenanceService,
)

from agents.quality_agent.services.validation_service import (
    ValidationService,
)


def make_rvu():
    text = (
        "The system shall update "
        "the owner information."
    )

    return RequirementValidationUnit(
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        ac_id="AC-X-01",

        atomic_text=text,

        behavior_type="FUNCTIONAL",

        source_text=text,

        source_fragment=text,

        source_span=SourceSpan(
            start=0,
            end=len(text),
        ),

        constraints=[],

        confidence=1.0,

        requires_review=False,

        version=1,

        extraction_method="TEST",
    )


def make_profile():
    return ExpectedEvidenceProfile(
        profile_id="PROFILE-X",

        rvu_id="REQ-X-RVU-01",

        requirement_id="REQ-X",

        ac_id="AC-X-01",

        requirement_type="FUNCTIONAL",

        requirement_subtype="FUNCTIONAL",

        evidence_type="FUNCTIONAL_TEST",

        support_status="SUPPORTED",
    )


def make_evidence(
    status: str,
):
    return ValidationEvidence(
        evidence_id="EV-X",

        evidence_type="MANUAL_TEST",

        title="Owner update test",

        description=(
            "Verify owner information "
            "can be updated."
        ),

        expected_result=(
            "Updated owner information "
            "is persisted."
        ),

        execution_status=status,

        source_path="test_fixture",

        source_tool="TEST",

        synthetic=False,

        metadata={},
    )


def make_adequate_summary():
    return RVUAdequacySummary(
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


def test_adequate_observed_passed_evidence_validates_rvu():
    evidence = make_evidence(
        "PASS"
    )

    ExecutionProvenanceService.mark_observed(
        evidence,

        status="PASS",

        source="TEST_EXECUTION",

        execution_id="RUN-001",

        executed_at=(
            "2026-10-23T"
            "00:00:00+05:30"
        ),

        actual_result=(
            "Expected result was "
            "successfully observed."
        ),
    )

    result = (
        ValidationService()
        .evaluate_rvus(
            rvus=[
                make_rvu()
            ],

            profiles=[
                make_profile()
            ],

            summaries=[
                make_adequate_summary()
            ],

            evidence=[
                evidence
            ],
        )[0]
    )

    assert (
        result.execution_satisfied
        is True
    )

    assert (
        result.validation_status
        == "VALIDATED"
    )


def test_adequate_observed_failed_evidence_is_not_validated():
    evidence = make_evidence(
        "FAIL"
    )

    ExecutionProvenanceService.mark_observed(
        evidence,

        status="FAIL",

        source="TEST_EXECUTION",

        execution_id="RUN-002",

        executed_at=(
            "2026-10-23T"
            "00:05:00+05:30"
        ),

        actual_result=(
            "Expected result was "
            "not achieved."
        ),
    )

    result = (
        ValidationService()
        .evaluate_rvus(
            rvus=[
                make_rvu()
            ],

            profiles=[
                make_profile()
            ],

            summaries=[
                make_adequate_summary()
            ],

            evidence=[
                evidence
            ],
        )[0]
    )

    assert (
        result.execution_satisfied
        is False
    )

    assert (
        result.validation_status
        == "PARTIAL"
    )


def test_adequate_synthetic_pass_does_not_validate_rvu():
    evidence = make_evidence(
        "PASS"
    )

    ExecutionProvenanceService.mark_controlled(
        evidence,

        controlled_outcome="PASS",

        source=(
            "C3_CONTROLLED_"
            "EXECUTION_FIXTURE"
        ),

        execution_id="CTRL-001",

        actual_result=(
            "Synthetic PASS for "
            "pipeline testing."
        ),
    )

    result = (
        ValidationService()
        .evaluate_rvus(
            rvus=[
                make_rvu()
            ],

            profiles=[
                make_profile()
            ],

            summaries=[
                make_adequate_summary()
            ],

            evidence=[
                evidence
            ],
        )[0]
    )

    assert (
        evidence.execution_status
        == "NOT_EXECUTED"
    )

    assert (
        evidence.metadata[
            "controlled_outcome"
        ]
        == "PASS"
    )

    assert (
        result.execution_satisfied
        is False
    )

    assert (
        result.validation_status
        == "PARTIAL"
    )


def test_adequate_not_executed_evidence_is_partial():
    evidence = make_evidence(
        "NOT_EXECUTED"
    )

    result = (
        ValidationService()
        .evaluate_rvus(
            rvus=[
                make_rvu()
            ],

            profiles=[
                make_profile()
            ],

            summaries=[
                make_adequate_summary()
            ],

            evidence=[
                evidence
            ],
        )[0]
    )

    assert (
        result.execution_satisfied
        is False
    )

    assert (
        result.validation_status
        == "PARTIAL"
    )