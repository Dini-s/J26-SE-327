import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.quality_agent.services.dataset_service import (
    DatasetService,
)


def test_save_and_load_json(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "nested"
        / "sample.json"
    )

    expected = {
        "name": "ASPIRE",
        "component": 3,
        "enabled": True,
    }

    DatasetService.save_json(
        path,
        expected,
    )

    assert path.exists()

    result = (
        DatasetService.load_json(
            path
        )
    )

    assert result == expected


def test_load_json_missing_file_raises(
    tmp_path: Path,
):
    missing_path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(
        FileNotFoundError,
        match=(
            "Required dataset file "
            "not found"
        ),
    ):
        DatasetService.load_json(
            missing_path
        )


def test_load_requirements_returns_models(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "requirements.json"
    )

    raw = [
        {
            "requirement_id": "REQ-001",
            "title": "Example Requirement",
            "text": (
                "The system shall "
                "perform an action."
            ),
            "type": "FUNCTIONAL",
            "subtype": "CREATE",
            "risk": "MEDIUM",
            "version": 1,
            "source": "TEST_FIXTURE",
            "acceptance_criteria": [
                {
                    "ac_id": "AC-001",
                    "text": (
                        "The system shall "
                        "create the record."
                    ),
                }
            ],
        }
    ]

    path.write_text(
        json.dumps(
            raw
        ),
        encoding="utf-8",
    )

    requirements = (
        DatasetService
        .load_requirements(
            path
        )
    )

    assert len(
        requirements
    ) == 1

    requirement = (
        requirements[0]
    )

    assert (
        requirement.requirement_id
        == "REQ-001"
    )

    assert (
        requirement.type
        == "FUNCTIONAL"
    )

    assert len(
        requirement
        .acceptance_criteria
    ) == 1

    assert (
        requirement
        .acceptance_criteria[0]
        .ac_id
        == "AC-001"
    )


def test_load_requirements_rejects_invalid_schema(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "invalid_requirements.json"
    )

    invalid = [
        {
            "requirement_id":
            "REQ-INVALID",

            # Required fields such as
            # title, text and source
            # are deliberately omitted.
            "type":
            "FUNCTIONAL",

            "subtype":
            "CREATE",

            "risk":
            "HIGH",

            "acceptance_criteria":
            [],
        }
    ]

    path.write_text(
        json.dumps(
            invalid
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValidationError
    ):
        DatasetService.load_requirements(
            path
        )