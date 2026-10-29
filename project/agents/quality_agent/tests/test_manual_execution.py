from types import SimpleNamespace

import pytest

from agents.quality_agent.services.manual_execution import (
    ManualExecutionService,
)


def make_manual_evidence(
    evidence_id: str = "MT-001",
):
    return SimpleNamespace(
        evidence_id=(
            evidence_id
        ),

        evidence_type=(
            "MANUAL_TEST"
        ),

        execution_status=(
            "NOT_EXECUTED"
        ),

        execution_run_id=None,

        synthetic=False,

        source_tool=(
            "C3_MANUAL_TEST"
        ),

        metadata={},
    )


def test_manual_execution_is_applied():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[
                {
                    "execution_id":
                        "RUN-001",

                    "evidence_id":
                        "MT-001",

                    "status":
                        "PASS",

                    "observed":
                        True,

                    "source_tool":
                        (
                            "MANUAL_"
                            "EXECUTION_RECORD"
                        ),

                    "executed_at":
                        (
                            "2026-10-23T"
                            "00:00:00+05:30"
                        ),

                    "actual_result":
                        (
                            "Expected result "
                            "was observed."
                        ),
                }
            ],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        == "PASS"
    )

    assert (
        item.metadata[
            "execution_observed"
        ]
        is True
    )

    assert (
        item.metadata[
            "execution_kind"
        ]
        == "OBSERVED"
    )


def test_missing_execution_remains_not_executed():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        == "NOT_EXECUTED"
    )

    assert (
        item.metadata[
            "execution_observed"
        ]
        is False
    )

    assert (
        item.metadata[
            "execution_kind"
        ]
        == "NOT_EXECUTED"
    )


def test_controlled_manual_pass_becomes_not_executed():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[
                {
                    "execution_id":
                        "CTRL-001",

                    "evidence_id":
                        "MT-001",

                    "status":
                        "PASS",

                    "observed":
                        False,

                    "synthetic":
                        True,

                    "source_tool":
                        (
                            "C3_CONTROLLED_"
                            "EXECUTION_FIXTURE"
                        ),

                    "actual_result":
                        (
                            "Synthetic PASS "
                            "for pipeline testing."
                        ),
                }
            ],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        == "NOT_EXECUTED"
    )

    assert (
        item.metadata[
            "execution_observed"
        ]
        is False
    )

    assert (
        item.metadata[
            "controlled_outcome"
        ]
        == "PASS"
    )

    assert (
        item.metadata[
            "execution_kind"
        ]
        == "CONTROLLED_FIXTURE"
    )


def test_controlled_manual_fail_becomes_not_executed():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[
                {
                    "execution_id":
                        "CTRL-002",

                    "evidence_id":
                        "MT-001",

                    "status":
                        "FAIL",

                    "observed":
                        False,

                    "synthetic":
                        True,

                    "source_tool":
                        (
                            "C3_CONTROLLED_"
                            "EXECUTION_FIXTURE"
                        ),
                }
            ],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        == "NOT_EXECUTED"
    )

    assert (
        item.metadata[
            "controlled_outcome"
        ]
        == "FAIL"
    )


def test_observed_manual_pass_is_preserved():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[
                {
                    "execution_id":
                        "MANUAL-001",

                    "evidence_id":
                        "MT-001",

                    "status":
                        "PASS",

                    "observed":
                        True,

                    "source_tool":
                        (
                            "MANUAL_"
                            "EXECUTION_RECORD"
                        ),

                    "executed_at":
                        (
                            "2026-10-23T"
                            "00:15:00+05:30"
                        ),

                    "executed_by":
                        "researcher",

                    "environment":
                        (
                            "Spring PetClinic "
                            "local"
                        ),

                    "actual_result":
                        (
                            "The expected "
                            "behaviour was "
                            "successfully observed."
                        ),
                }
            ],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        == "PASS"
    )

    assert (
        item.metadata[
            "execution_observed"
        ]
        is True
    )

    assert (
        item.execution_run_id
        == "MANUAL-001"
    )


def test_observed_pass_requires_execution_metadata():
    evidence = (
        make_manual_evidence()
    )

    with pytest.raises(
        ValueError
    ):
        (
            ManualExecutionService()
            .apply_records(
                evidence=[
                    evidence
                ],

                records=[
                    {
                        "evidence_id":
                            "MT-001",

                        "status":
                            "PASS",

                        "observed":
                            True,

                        "actual_result":
                            "Passed.",
                    }
                ],
            )
        )


def test_duplicate_manual_execution_is_rejected():
    evidence = (
        make_manual_evidence()
    )

    records = [
        {
            "evidence_id":
                "MT-001",

            "status":
                "PASS",

            "observed":
                False,
        },
        {
            "evidence_id":
                "MT-001",

            "status":
                "PASS",

            "observed":
                False,
        },
    ]

    with pytest.raises(
        ValueError
    ):
        (
            ManualExecutionService()
            .apply_records(
                evidence=[
                    evidence
                ],

                records=records,
            )
        )


def test_blocked_manual_execution_becomes_not_executed():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[
                {
                    "execution_id":
                        "BLOCKED-001",

                    "evidence_id":
                        "MT-001",

                    "status":
                        "BLOCKED",

                    "observed":
                        False,

                    "source_tool":
                        (
                            "MANUAL_"
                            "EXECUTION_RECORD"
                        ),

                    "blocked_reason":
                        (
                            "Required test "
                            "precondition unavailable."
                        ),
                }
            ],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        == "NOT_EXECUTED"
    )

    assert (
        item.metadata[
            "execution_observed"
        ]
        is False
    )

    assert (
        item.metadata[
            "execution_kind"
        ]
        == "BLOCKED"
    )

    assert (
        item.metadata[
            "original_execution_status"
        ]
        == "BLOCKED"
    )


def test_blocked_is_not_treated_as_controlled_pass():
    evidence = (
        make_manual_evidence()
    )

    result = (
        ManualExecutionService()
        .apply_records(
            evidence=[
                evidence
            ],

            records=[
                {
                    "execution_id":
                        "BLOCKED-002",

                    "evidence_id":
                        "MT-001",

                    "status":
                        "BLOCKED",

                    "observed":
                        False,

                    "source_tool":
                        (
                            "MANUAL_"
                            "EXECUTION_RECORD"
                        ),
                }
            ],
        )
    )

    item = result[0]

    assert (
        item.execution_status
        != "PASS"
    )

    assert (
        item.execution_status
        != "FAIL"
    )

    assert (
        item.execution_status
        == "NOT_EXECUTED"
    )


def test_unknown_status_is_rejected():
    evidence = (
        make_manual_evidence()
    )

    with pytest.raises(
        ValueError
    ):
        (
            ManualExecutionService()
            .apply_records(
                evidence=[
                    evidence
                ],

                records=[
                    {
                        "evidence_id":
                            "MT-001",

                        "status":
                            "SOMETHING_UNKNOWN",
                    }
                ],
            )
        )