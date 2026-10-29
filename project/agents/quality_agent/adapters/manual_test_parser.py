import json
from pathlib import Path

from agents.quality_agent.schemas import (
    ValidationEvidence,
)


class ManualTestParser:
    def parse(
        self,
        path: Path,
    ) -> list[ValidationEvidence]:

        if not path.exists():
            return []

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw = json.load(file)

        evidence: list[
            ValidationEvidence
        ] = []

        for item in raw:
            evidence.append(
                ValidationEvidence(
                    evidence_id=(
                        item[
                            "evidence_id"
                        ]
                    ),
                    evidence_type=(
                        "MANUAL_TEST"
                    ),
                    title=item[
                        "title"
                    ],
                    description=(
                        item.get(
                            "description",
                            "",
                        )
                    ),
                    preconditions=(
                        item.get(
                            "preconditions",
                            [],
                        )
                    ),
                    inputs=item.get(
                        "inputs",
                        [],
                    ),
                    steps=item.get(
                        "steps",
                        [],
                    ),
                    expected_result=(
                        item.get(
                            "expected_result"
                        )
                    ),
                    assertions=(
                        item.get(
                            "assertions",
                            [],
                        )
                    ),
                    execution_status=(
                        item.get(
                            "execution_status"
                        )
                    ),
                    source_path=str(
                        path
                    ),
                    source_tool=(
                        item.get(
                            "source_tool",
                            (
                                "C3_MANUAL_"
                                "CURATED"
                            ),
                        )
                    ),
                    source_version=(
                        item.get(
                            "source_version",
                            "1.0",
                        )
                    ),
                    raw_reference=(
                        item[
                            "evidence_id"
                        ]
                    ),
                    synthetic=(
                        item.get(
                            "synthetic",
                            False,
                        )
                    ),
                )
            )

        return evidence