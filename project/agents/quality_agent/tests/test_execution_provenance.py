from types import SimpleNamespace

from agents.quality_agent.services.execution_provenance import (
    ExecutionProvenanceService,
)


def make_evidence(
    *,
    evidence_type="MANUAL_TEST",
    status="NOT_EXECUTED",
    run_id=None,
    synthetic=False,
    source_tool="TEST",
    metadata=None,
):
    return SimpleNamespace(
        evidence_id="EV-001",

        evidence_type=(
            evidence_type
        ),

        execution_status=(
            status
        ),

        execution_run_id=(
            run_id
        ),

        synthetic=(
            synthetic
        ),

        source_tool=(
            source_tool
        ),

        metadata=(
            metadata
            or {}
        ),
    )


def test_synthetic_pass_is_not_observed():
    item = make_evidence(
        status="PASS",

        synthetic=True,

        source_tool=(
            "C3_CONTROLLED_FIXTURE"
        ),
    )

    assert (
        ExecutionProvenanceService
        .is_observed(
            item
        )
        is False
    )


def test_explicit_controlled_result_is_not_observed():
    item = make_evidence(
        status="PASS",

        metadata={
            "execution_observed":
                False,

            "execution_kind":
                "CONTROLLED_FIXTURE",
        },
    )

    assert (
        ExecutionProvenanceService
        .is_observed(
            item
        )
        is False
    )


def test_real_manual_execution_is_observed():
    item = make_evidence(
        status="PASS",

        metadata={
            "execution_observed":
                True,

            "execution_kind":
                "OBSERVED",
        },
    )

    assert (
        ExecutionProvenanceService
        .is_observed(
            item
        )
        is True
    )

    assert (
        ExecutionProvenanceService
        .is_qualifying_pass(
            item
        )
        is True
    )


def test_real_automated_run_is_observed():
    item = make_evidence(
        evidence_type=(
            "AUTOMATED_TEST"
        ),

        status="PASS",

        run_id=(
            "surefire-run-001"
        ),

        source_tool=(
            "MAVEN_SUREFIRE"
        ),
    )

    assert (
        ExecutionProvenanceService
        .is_observed(
            item
        )
        is True
    )


def test_synthetic_performance_run_is_not_observed():
    item = make_evidence(
        evidence_type=(
            "PERFORMANCE_EVIDENCE"
        ),

        status="PASS",

        run_id=(
            "synthetic-perf-001"
        ),

        synthetic=True,

        source_tool=(
            "C3_CONTROLLED_FIXTURE"
        ),
    )

    assert (
        ExecutionProvenanceService
        .is_observed(
            item
        )
        is False
    )


def test_controlled_pass_display_becomes_not_executed():
    item = make_evidence(
        status="NOT_EXECUTED",

        metadata={
            "execution_observed":
                False,

            "execution_kind":
                "CONTROLLED_FIXTURE",

            "controlled_outcome":
                "PASS",
        },
    )

    state = (
        ExecutionProvenanceService
        .display_state(
            item
        )
    )

    assert (
        state["label"]
        == "Not Executed"
    )

    assert (
        state["observed"]
        is False
    )


def test_observed_pass_display():
    item = make_evidence(
        status="PASS",

        metadata={
            "execution_observed":
                True,

            "execution_kind":
                "OBSERVED",
        },
    )

    state = (
        ExecutionProvenanceService
        .display_state(
            item
        )
    )

    assert (
        state["label"]
        == "Observed PASS"
    )

    assert (
        state["detail"]
        == "Execution confirmed"
    )