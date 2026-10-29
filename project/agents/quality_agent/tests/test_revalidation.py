from agents.quality_agent.schemas import (
    RevalidationChangeCase,
    RevalidationEvidenceInput,
)

from agents.quality_agent.services.revalidation import (
    RevalidationService,
)


def make_case():
    return RevalidationChangeCase(
        change_id="CHG-TEST-001",

        source=(
            "C3_CONTROLLED_"
            "REVALIDATION_FIXTURE"
        ),

        requirement_id=(
            "REQ-TEST-001"
        ),

        requirement_type=(
            "FUNCTIONAL"
        ),

        requirement_subtype=(
            "VALIDATION"
        ),

        affected_rvu_ids=[
            "REQ-TEST-001-RVU-01"
        ],

        change_type=(
            "ACCEPTANCE_CRITERION_UPDATE"
        ),

        previous_text=(
            "The value shall remain "
            "valid for 30 minutes."
        ),

        current_text=(
            "The value shall remain "
            "valid for 45 minutes."
        ),

        change_description=(
            "Controlled test change."
        ),

        evidence_cases=[
            RevalidationEvidenceInput(
                evidence_id="EV-1",

                evidence_name=(
                    "unchangedBehaviorTest"
                ),

                evidence_text=(
                    "Validate unchanged "
                    "core behavior."
                ),

                previous_validation_purpose=(
                    "Validate core behavior."
                ),

                current_validation_purpose=(
                    "Validate core behavior."
                ),
            ),

            RevalidationEvidenceInput(
                evidence_id="EV-2",

                evidence_name=(
                    "old30MinuteTest"
                ),

                evidence_text=(
                    "Verify behavior for "
                    "30 minutes."
                ),

                previous_validation_purpose=(
                    "Validate behavior "
                    "for 30 minutes."
                ),

                current_validation_purpose=(
                    "Validate behavior "
                    "for 45 minutes."
                ),
            ),

            RevalidationEvidenceInput(
                evidence_id="EV-3",

                evidence_name=(
                    "boundaryAt30Minutes"
                ),

                evidence_text=(
                    "Boundary validation "
                    "at 30 minutes."
                ),

                previous_validation_purpose=(
                    "Validate the boundary "
                    "at 30 minutes."
                ),

                current_validation_purpose=(
                    "Validate the boundary "
                    "at 45 minutes."
                ),
            ),

            RevalidationEvidenceInput(
                evidence_id=None,

                evidence_name=(
                    "new45MinuteEvidence"
                ),

                evidence_text=(
                    "No existing evidence."
                ),

                previous_validation_purpose=(
                    "Not applicable."
                ),

                current_validation_purpose=(
                    "Validate the new "
                    "45 minute behavior."
                ),
            ),
        ],
    )


def test_revalidation_produces_all_four_classes():
    report = (
        RevalidationService()
        .analyze(
            make_case()
        )
    )

    assert (
        report.reusable_count
        == 1
    )

    assert (
        report
        .modification_required_count
        == 1
    )

    assert (
        report.outdated_count
        == 1
    )

    assert (
        report
        .new_evidence_required_count
        == 1
    )


def test_reusable_evidence_is_kept():
    report = (
        RevalidationService()
        .analyze(
            make_case()
        )
    )

    reusable = next(
        item
        for item
        in report.decisions
        if (
            item.classification
            == "REUSABLE"
        )
    )

    assert reusable.action == "KEEP"


def test_old_constraint_evidence_is_outdated():
    report = (
        RevalidationService()
        .analyze(
            make_case()
        )
    )

    outdated = next(
        item
        for item
        in report.decisions
        if (
            item.classification
            == "OUTDATED"
        )
    )

    assert (
        outdated.action
        == "REPLACE"
    )


def test_boundary_evidence_is_modified():
    report = (
        RevalidationService()
        .analyze(
            make_case()
        )
    )

    modified = next(
        item
        for item
        in report.decisions
        if (
            item.classification
            == "MODIFICATION_REQUIRED"
        )
    )

    assert (
        modified.action
        == "UPDATE"
    )


def test_missing_evidence_requires_creation():
    report = (
        RevalidationService()
        .analyze(
            make_case()
        )
    )

    new_item = next(
        item
        for item
        in report.decisions
        if (
            item.classification
            == "NEW_EVIDENCE_REQUIRED"
        )
    )

    assert (
        new_item.action
        == "CREATE"
    )