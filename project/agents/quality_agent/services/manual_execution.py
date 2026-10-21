from __future__ import annotations

import json

from datetime import datetime

from pathlib import Path

from typing import Literal

from pydantic import (
    BaseModel,
    TypeAdapter,
)

from agents.quality_agent.schemas import (
    ValidationEvidence,
)


ManualExecutionStatus = Literal[
    "PASS",
    "FAIL",
    "BLOCKED",
    "SKIPPED",
    "NOT_EXECUTED",
]


class ManualExecutionRecord(
    BaseModel
):
    execution_id: str

    evidence_id: str

    status: ManualExecutionStatus

    executed_at: (
        datetime | None
    ) = None

    executed_by: (
        str | None
    ) = None

    environment: (
        str | None
    ) = None

    actual_result: (
        str | None
    ) = None

    notes: (
        str | None
    ) = None

    execution_source: str

    source_version: str = "1.0"

    synthetic: bool = False


class ManualExecutionService:
    """
    Adds manual execution results to normalized
    MANUAL_TEST evidence.

    Manual test definitions and manual execution
    results remain separate artifacts.

    A controlled execution fixture may populate
    execution status for demonstration and
    evaluation but remains explicitly marked
    synthetic in provenance metadata.
    """

    def load(
        self,
        path: Path,
    ) -> list[
        ManualExecutionRecord
    ]:

        if not path.exists():
            return []

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            raw = json.load(
                handle
            )

        records = TypeAdapter(
            list[
                ManualExecutionRecord
            ]
        ).validate_python(
            raw
        )

        execution_ids = [
            item.execution_id
            for item
            in records
        ]

        if (
            len(execution_ids)
            != len(
                set(
                    execution_ids
                )
            )
        ):
            raise ValueError(
                "Duplicate manual execution "
                "IDs were found."
            )

        evidence_ids = [
            item.evidence_id
            for item
            in records
        ]

        if (
            len(evidence_ids)
            != len(
                set(
                    evidence_ids
                )
            )
        ):
            raise ValueError(
                "Multiple manual execution "
                "records reference the same "
                "evidence ID. Keep only the "
                "latest/current execution in "
                "manual_execution_results.json."
            )

        return records

    def apply(
        self,
        *,
        evidence: list[
            ValidationEvidence
        ],
        path: Path,
    ) -> list[
        ValidationEvidence
    ]:

        records = self.load(
            path
        )

        record_map = {
            item.evidence_id:
            item

            for item
            in records
        }

        manual_evidence_ids = {
            item.evidence_id

            for item
            in evidence

            if (
                item.evidence_type
                == "MANUAL_TEST"
            )
        }

        unknown = sorted(
            set(
                record_map
            )
            - manual_evidence_ids
        )

        if unknown:
            raise ValueError(
                (
                    "Manual execution records "
                    "reference unknown or "
                    "non-manual evidence IDs: "
                    + ", ".join(
                        unknown
                    )
                )
            )

        output: list[
            ValidationEvidence
        ] = []

        for item in evidence:
            if (
                item.evidence_type
                != "MANUAL_TEST"
            ):
                output.append(
                    item
                )

                continue

            record = record_map.get(
                item.evidence_id
            )

            if record is None:
                output.append(
                    item.model_copy(
                        update={
                            "execution_status":
                                "NOT_EXECUTED",

                            "execution_run_id":
                                None,
                        }
                    )
                )

                continue

            metadata = dict(
                item.metadata
            )

            metadata[
                "manual_execution"
            ] = (
                record.model_dump(
                    mode="json"
                )
            )

            output.append(
                item.model_copy(
                    update={
                        "execution_status":
                            record.status,

                        "execution_run_id":
                            record.execution_id,

                        "metadata":
                            metadata,
                    }
                )
            )

        return output