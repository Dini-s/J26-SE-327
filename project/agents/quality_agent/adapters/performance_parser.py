import json
from pathlib import Path

from agents.quality_agent.schemas import (
    ValidationEvidence,
)


class PerformanceEvidenceParser:
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

        evidence = []

        for item in raw:
            evidence.append(
                ValidationEvidence(
                    evidence_id=(
                        item[
                            "evidence_id"
                        ]
                    ),
                    evidence_type=(
                        "PERFORMANCE_EVIDENCE"
                    ),
                    title=(
                        item["title"]
                    ),
                    description=(
                        item.get(
                            "description",
                            "",
                        )
                    ),
                    execution_status=(
                        item.get(
                            "execution_status"
                        )
                    ),
                    metric=item.get(
                        "metric"
                    ),
                    measured_value=(
                        item.get(
                            "measured_value"
                        )
                    ),
                    threshold=(
                        item.get(
                            "threshold"
                        )
                    ),
                    percentile=(
                        item.get(
                            "percentile"
                        )
                    ),
                    load=item.get(
                        "load"
                    ),
                    duration_seconds=(
                        item.get(
                            "duration_seconds"
                        )
                    ),
                    scope=item.get(
                        "scope"
                    ),
                    unit=item.get(
                        "unit"
                    ),
                    source_path=str(
                        path
                    ),
                    source_tool=(
                        item.get(
                            "source_tool",
                            (
                                "C3_CONTROLLED_"
                                "PERFORMANCE_"
                                "FIXTURE"
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
                            True,
                        )
                    ),
                    metadata={
                        "configuration":
                        item.get(
                            "configuration",
                            {},
                        )
                    },
                )
            )

        return evidence