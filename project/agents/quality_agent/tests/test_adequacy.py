from agents.quality_agent.schemas import (
    CandidateEvidenceMatch,
    ExpectedEvidenceProfile,
    RequirementValidationUnit,
    SourceSpan,
    ValidationEvidence,
)

from agents.quality_agent.services.adequacy import (
    AdequacyEngine,
)


def make_rvu(
    behavior="NEGATIVE",
):
    return RequirementValidationUnit(
        rvu_id="RVU-1",

        requirement_id="REQ-1",

        ac_id="AC-1",

        atomic_text=(
            "The system shall reject "
            "an invalid request."
        ),

        behavior_type=behavior,

        source_text=(
            "The system shall reject "
            "an invalid request."
        ),

        source_fragment=(
            "reject an invalid request"
        ),

        source_span=SourceSpan(
            start=0,
            end=25,
        ),

        constraints=[],

        confidence=1.0,

        extraction_method="TEST",
    )


def make_profile():
    return ExpectedEvidenceProfile(
        profile_id="PROFILE-1",

        rvu_id="RVU-1",

        requirement_id="REQ-1",

        ac_id="AC-1",

        requirement_type="FUNCTIONAL",

        requirement_subtype="VALIDATION",

        evidence_type="AUTOMATED_TEST",

        required_scenarios=[
            "negative"
        ],

        expected_outcomes=[
            "invalid request rejected"
        ],
    )


def make_match(
    score=0.90,
):
    return CandidateEvidenceMatch(
        rvu_id="RVU-1",

        evidence_id="EV-1",

        evidence_title=(
            "rejectInvalidRequest"
        ),

        evidence_type="AUTOMATED_TEST",

        retrieval_method="semantic",

        similarity_score=score,

        rank=1,

        model_name="test-model",

        source_path="test.py",

        source_tool="pytest",
    )


def test_strong_functional_evidence_is_adequate():

    evidence = ValidationEvidence(
        evidence_id="EV-1",

        evidence_type="AUTOMATED_TEST",

        title=(
            "reject invalid request"
        ),

        description=(
            "Verify invalid request "
            "is rejected."
        ),

        assertions=[
            "assert rejected response"
        ],

        execution_status="PASS",

        source_path="test.py",

        source_tool="pytest",
    )

    result = (
        AdequacyEngine()
        .assess(
            profile=make_profile(),
            rvu=make_rvu(),
            match=make_match(),
            evidence=evidence,
        )
    )

    assert (
        result.adequacy_status
        == "ADEQUATE"
    )


def test_low_relevance_is_not_adequate():

    evidence = ValidationEvidence(
        evidence_id="EV-1",

        evidence_type="AUTOMATED_TEST",

        title="unrelated test",

        assertions=[
            "assert something"
        ],

        execution_status="PASS",

        source_path="test.py",

        source_tool="pytest",
    )

    result = (
        AdequacyEngine()
        .assess(
            profile=make_profile(),
            rvu=make_rvu(),
            match=make_match(
                0.10
            ),
            evidence=evidence,
        )
    )

    assert (
        result.adequacy_status
        != "ADEQUATE"
    )


def test_pass_does_not_override_weak_oracle():

    evidence = ValidationEvidence(
        evidence_id="EV-1",

        evidence_type="MANUAL_TEST",

        title=(
            "invalid request test"
        ),

        expected_result="works correctly",

        execution_status="PASS",

        source_path="manual.json",

        source_tool="manual",
    )

    result = (
        AdequacyEngine()
        .assess(
            profile=make_profile(),
            rvu=make_rvu(),
            match=make_match(),
            evidence=evidence,
        )
    )

    assert (
        result.adequacy_status
        != "ADEQUATE"
    )


def test_review_required_nfr_not_falsely_adequate():

    profile = ExpectedEvidenceProfile(
        profile_id="P-NFR",

        rvu_id="RVU-1",

        requirement_id="REQ-1",

        ac_id="AC-1",

        requirement_type=(
            "NON_FUNCTIONAL"
        ),

        requirement_subtype=(
            "RELIABILITY"
        ),

        evidence_type=(
            "RELIABILITY_EVIDENCE"
        ),

        support_status=(
            "REVIEW_REQUIRED"
        ),
    )

    evidence = ValidationEvidence(
        evidence_id="EV-1",

        evidence_type="MANUAL_TEST",

        title="reliability review",

        execution_status="PASS",

        source_path="manual.json",

        source_tool="manual",
    )

    result = (
        AdequacyEngine()
        .assess(
            profile=profile,
            rvu=make_rvu(),
            match=make_match(),
            evidence=evidence,
        )
    )

    assert (
        result.adequacy_status
        == "NOT_ASSESSED"
    )