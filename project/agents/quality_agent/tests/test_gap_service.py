from agents.quality_agent.schemas import (
    RVUAdequacySummary,
    RVUValidationResult,
)

from agents.quality_agent.services.gap_service import (
    GapService,
)


def test_missing_evidence_generates_gap():
    validation = RVUValidationResult(
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        evidence_found=False,
        adequacy_status="INADEQUATE",
        execution_satisfied=False,
        validation_status="UNSATISFIED",
        reason_codes=[
            "NO_RELEVANT_EVIDENCE"
        ],
    )

    summary = RVUAdequacySummary(
        rvu_id="REQ-X-RVU-01",
        requirement_id="REQ-X",
        support_status="SUPPORTED",
        evidence_found=False,
        adequacy_status="INADEQUATE",
        reason_codes=[
            "NO_RELEVANT_EVIDENCE"
        ],
    )

    gaps, recommendations = (
        GapService().generate(
            validations=[
                validation
            ],
            summaries=[
                summary
            ],
        )
    )

    assert len(gaps) == 1

    assert (
        gaps[0].gap_type
        == "MISSING_EVIDENCE"
    )

    assert len(
        recommendations
    ) == 1