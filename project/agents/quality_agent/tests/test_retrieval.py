from agents.quality_agent.schemas import (
    RequirementValidationUnit,
    SourceSpan,
    ValidationEvidence,
)

from agents.quality_agent.services.retrieval import (
    EvidenceRetrievalService,
)


def make_rvu():
    text = (
        "The system shall reject "
        "an expired reset token."
    )

    return RequirementValidationUnit(
        rvu_id=(
            "REQ-X-RVU-01"
        ),

        requirement_id=(
            "REQ-X"
        ),

        ac_id="AC-X",

        atomic_text=text,

        behavior_type=(
            "NEGATIVE"
        ),

        source_text=text,

        source_fragment=text,

        source_span=SourceSpan(
            start=0,
            end=len(text),
        ),

        constraints=[],

        confidence=0.95,

        requires_review=False,

        extraction_method=(
            "TEST"
        ),
    )


def make_evidence():
    return [
        ValidationEvidence(
            evidence_id="EV-1",

            evidence_type=(
                "MANUAL_TEST"
            ),

            title=(
                "Reject expired password "
                "reset token"
            ),

            description=(
                "Validate token expiry."
            ),

            expected_result=(
                "Expired reset token "
                "is rejected."
            ),

            source_path="test",

            source_tool="TEST",
        ),

        ValidationEvidence(
            evidence_id="EV-2",

            evidence_type=(
                "MANUAL_TEST"
            ),

            title=(
                "Change application theme"
            ),

            description=(
                "UI theme test."
            ),

            expected_result=(
                "Theme changes."
            ),

            source_path="test",

            source_tool="TEST",
        ),
    ]


def test_keyword_relevant_first():

    service = (
        EvidenceRetrievalService(
            "sentence-transformers/"
            "all-MiniLM-L6-v2"
        )
    )

    results = service.retrieve(
        make_rvu(),
        make_evidence(),
        "keyword",
        2,
    )

    assert (
        results[0].evidence_id
        == "EV-1"
    )


def test_tfidf_relevant_first():

    service = (
        EvidenceRetrievalService(
            "sentence-transformers/"
            "all-MiniLM-L6-v2"
        )
    )

    results = service.retrieve(
        make_rvu(),
        make_evidence(),
        "tfidf",
        2,
    )

    assert (
        results[0].evidence_id
        == "EV-1"
    )