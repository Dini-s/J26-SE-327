import json
from pathlib import Path

import pytest

from agents.quality_agent import config
from agents.quality_agent.agent import (
    QualityAgent,
)


@pytest.fixture
def isolated_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """
    Create a fully isolated Component 3 dataset.

    The test never writes to the real research
    corpus or processed Component 3 outputs.
    """

    data_root = (
        tmp_path
        / "component3"
    )

    raw_root = (
        data_root
        / "raw"
    )

    processed_root = (
        data_root
        / "processed"
    )

    requirements_path = (
        raw_root
        / "requirements"
        / "requirements.json"
    )

    manual_tests_path = (
        raw_root
        / "manual_tests"
        / "manual_tests.json"
    )

    junit_root = (
        raw_root
        / "junit"
        / "petclinic"
    )

    surefire_root = (
        raw_root
        / "surefire"
        / "petclinic"
    )

    performance_path = (
        raw_root
        / "performance"
        / "performance_evidence.json"
    )

    rvus_path = (
        processed_root
        / "rvus"
        / "rvus.json"
    )

    profiles_path = (
        processed_root
        / "evidence_profiles"
        / "evidence_profiles.json"
    )

    evidence_path = (
        processed_root
        / "normalized_evidence"
        / "evidence.json"
    )

    retrieval_root = (
        processed_root
        / "retrieval"
    )

    requirements_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manual_tests_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    performance_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    junit_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    surefire_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    requirements = [
        {
            "requirement_id": "REQ-TEST-001",
            "title": "Reject Invalid Token",
            "text": (
                "The system shall reject "
                "an invalid token."
            ),
            "type": "FUNCTIONAL",
            "subtype": "VALIDATION",
            "risk": "HIGH",
            "version": 1,
            "source": "TEST_FIXTURE",
            "acceptance_criteria": [
                {
                    "ac_id": "AC-TEST-001",
                    "text": (
                        "The system shall reject "
                        "an invalid token."
                    ),
                }
            ],
        }
    ]

    manual_tests = [
        {
            "evidence_id": "MT-TEST-001",
            "title": (
                "Reject invalid token"
            ),
            "description": (
                "Manual negative validation "
                "for an invalid token."
            ),
            "preconditions": [
                (
                    "The validation workflow "
                    "is available."
                )
            ],
            "inputs": [
                "Invalid token"
            ],
            "steps": [
                (
                    "Submit the invalid token."
                )
            ],
            "expected_result": (
                "The invalid token is rejected."
            ),
            "execution_status": (
                "NOT_EXECUTED"
            ),
            "source_tool": (
                "TEST_FIXTURE"
            ),
            "source_version": "1.0",
            "synthetic": True,
        }
    ]

    requirements_path.write_text(
        json.dumps(
            requirements,
            indent=2,
        ),
        encoding="utf-8",
    )

    manual_tests_path.write_text(
        json.dumps(
            manual_tests,
            indent=2,
        ),
        encoding="utf-8",
    )

    performance_path.write_text(
        "[]",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        config,
        "DATA_ROOT",
        data_root,
    )

    monkeypatch.setattr(
        config,
        "RAW_ROOT",
        raw_root,
    )

    monkeypatch.setattr(
        config,
        "PROCESSED_ROOT",
        processed_root,
    )

    monkeypatch.setattr(
        config,
        "REQUIREMENTS_PATH",
        requirements_path,
    )

    monkeypatch.setattr(
        config,
        "MANUAL_TESTS_PATH",
        manual_tests_path,
    )

    monkeypatch.setattr(
        config,
        "JUNIT_ROOT",
        junit_root,
    )

    monkeypatch.setattr(
        config,
        "SUREFIRE_ROOT",
        surefire_root,
    )

    monkeypatch.setattr(
        config,
        "PERFORMANCE_PATH",
        performance_path,
    )

    monkeypatch.setattr(
        config,
        "RVUS_PATH",
        rvus_path,
    )

    monkeypatch.setattr(
        config,
        "EVIDENCE_PROFILES_PATH",
        profiles_path,
    )

    monkeypatch.setattr(
        config,
        "NORMALIZED_EVIDENCE_PATH",
        evidence_path,
    )

    monkeypatch.setattr(
        config,
        "RETRIEVAL_ROOT",
        retrieval_root,
    )

    agent = QualityAgent()

    return {
        "agent": agent,
        "rvus_path": rvus_path,
        "profiles_path": profiles_path,
        "evidence_path": evidence_path,
        "retrieval_root": retrieval_root,
    }


def test_agent_processes_requirements(
    isolated_agent,
):
    agent = isolated_agent[
        "agent"
    ]

    result = (
        agent.process_requirements()
    )

    assert len(
        result["requirements"]
    ) == 1

    assert len(
        result["rvus"]
    ) == 1

    assert len(
        result["profiles"]
    ) == 1

    assert (
        result["rvus"][0]
        .requirement_id
        == "REQ-TEST-001"
    )

    assert (
        result["profiles"][0]
        .rvu_id
        == result["rvus"][0]
        .rvu_id
    )

    assert (
        isolated_agent[
            "rvus_path"
        ].exists()
    )

    assert (
        isolated_agent[
            "profiles_path"
        ].exists()
    )


def test_agent_normalizes_evidence(
    isolated_agent,
):
    agent = isolated_agent[
        "agent"
    ]

    evidence = (
        agent.normalize_evidence()
    )

    assert len(
        evidence
    ) == 1

    assert (
        evidence[0]
        .evidence_id
        == "MT-TEST-001"
    )

    assert (
        evidence[0]
        .evidence_type
        == "MANUAL_TEST"
    )

    assert (
        evidence[0]
        .execution_status
        == "NOT_EXECUTED"
    )

    assert (
        isolated_agent[
            "evidence_path"
        ].exists()
    )


def test_agent_overview_before_processing(
    isolated_agent,
):
    agent = isolated_agent[
        "agent"
    ]

    overview = (
        agent.overview()
    )

    assert (
        overview.requirements
        == 1
    )

    assert (
        overview.acceptance_criteria
        == 1
    )

    assert (
        overview.functional_requirements
        == 1
    )

    assert (
        overview.non_functional_requirements
        == 0
    )

    assert (
        overview.rvus
        == 0
    )

    assert (
        overview.expected_profiles
        == 0
    )

    assert (
        overview.evidence_items
        == 0
    )


def test_agent_overview_after_processing(
    isolated_agent,
):
    agent = isolated_agent[
        "agent"
    ]

    agent.process_requirements()
    agent.normalize_evidence()

    overview = (
        agent.overview()
    )

    assert (
        overview.requirements
        == 1
    )

    assert (
        overview.acceptance_criteria
        == 1
    )

    assert (
        overview.rvus
        == 1
    )

    assert (
        overview.expected_profiles
        == 1
    )

    assert (
        overview.evidence_items
        == 1
    )

    assert (
        overview.manual_tests
        == 1
    )

    assert (
        overview.automated_tests
        == 0
    )

    assert (
        overview.performance_evidence
        == 0
    )


def test_agent_keyword_retrieval(
    isolated_agent,
):
    agent = isolated_agent[
        "agent"
    ]

    result = (
        agent.process_requirements()
    )

    agent.normalize_evidence()

    rvu_id = (
        result["rvus"][0]
        .rvu_id
    )

    matches = agent.retrieve(
        rvu_id=rvu_id,
        method="keyword",
        top_k=1,
    )

    assert len(
        matches
    ) == 1

    assert (
        matches[0]
        .rvu_id
        == rvu_id
    )

    assert (
        matches[0]
        .evidence_id
        == "MT-TEST-001"
    )

    output_path = (
        isolated_agent[
            "retrieval_root"
        ]
        / f"{rvu_id}_keyword.json"
    )

    assert (
        output_path.exists()
    )


def test_agent_rejects_unknown_rvu(
    isolated_agent,
):
    agent = isolated_agent[
        "agent"
    ]

    agent.process_requirements()
    agent.normalize_evidence()

    with pytest.raises(
        ValueError,
        match="RVU not found",
    ):
        agent.retrieve(
            rvu_id=(
                "RVU-DOES-NOT-EXIST"
            ),
            method="keyword",
            top_k=1,
        )