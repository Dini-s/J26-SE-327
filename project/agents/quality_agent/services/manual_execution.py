from __future__ import annotations

import json

from pathlib import Path
from typing import Any

from agents.quality_agent.services.execution_provenance import (
    ExecutionProvenanceService,
)


class ManualExecutionService:
    """
    Applies manual execution-result records to normalized
    manual-test evidence.

    Execution semantics:

    Real observed PASS:
        -> execution_status = PASS
        -> execution_observed = True
        -> may confirm validation if evidence is ADEQUATE

    Real observed FAIL:
        -> execution_status = FAIL
        -> execution_observed = True
        -> execution happened, but RVU is not validated

    Controlled/synthetic PASS or FAIL:
        -> controlled_outcome preserves PASS/FAIL
        -> execution_status = NOT_EXECUTED
        -> execution_observed = False
        -> cannot confirm validation

    BLOCKED:
        -> original_status = BLOCKED
        -> execution_status = NOT_EXECUTED
        -> cannot confirm validation

    Missing result:
        -> execution_status = NOT_EXECUTED
    """

    VALID_STATUSES = {
        "PASS",
        "FAIL",
        "SKIPPED",
        "NOT_EXECUTED",
        "ERROR",
        "BLOCKED",
    }

    def __init__(
        self,
        results_path: str | Path | None = None,
    ):
        self.results_path = (
            Path(results_path)
            if results_path
            else None
        )

    def apply(
        self,
        evidence: list[Any],
        results_path: str | Path | None = None,
        path: str | Path | None = None,
    ) -> list[Any]:
        """
        Apply manual execution results.

        Both `results_path` and `path` are accepted because the
        existing QualityAgent currently calls this service using
        `path=...`.
        """

        selected_path = (
            results_path
            if results_path is not None
            else path
        )

        selected_path = (
            Path(selected_path)
            if selected_path is not None
            else self.results_path
        )

        if selected_path is None:
            return self._sanitize_existing(
                evidence
            )

        if not selected_path.exists():
            return self._sanitize_existing(
                evidence
            )

        with selected_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw = json.load(
                file
            )

        records = (
            self._extract_records(
                raw
            )
        )

        return self.apply_records(
            evidence=evidence,
            records=records,
        )

    def merge(
        self,
        evidence: list[Any],
        results: (
            list[dict[str, Any]]
            | dict[str, Any]
            | str
            | Path
        ),
    ) -> list[Any]:
        if isinstance(
            results,
            (
                str,
                Path,
            ),
        ):
            return self.apply(
                evidence=evidence,
                results_path=results,
            )

        records = (
            self._extract_records(
                results
            )
        )

        return self.apply_records(
            evidence=evidence,
            records=records,
        )

    def apply_results(
        self,
        evidence: list[Any],
        results: (
            list[dict[str, Any]]
            | dict[str, Any]
            | str
            | Path
        ),
    ) -> list[Any]:
        return self.merge(
            evidence=evidence,
            results=results,
        )

    def apply_records(
        self,
        *,
        evidence: list[Any],
        records: list[dict[str, Any]],
    ) -> list[Any]:
        validated_records = (
            self._validate_records(
                records
            )
        )

        result_map = {
            record["evidence_id"]: record
            for record
            in validated_records
        }

        for item in evidence:
            evidence_type = str(
                getattr(
                    item,
                    "evidence_type",
                    "",
                )
                or ""
            ).upper()

            if evidence_type not in {
                "MANUAL_TEST",
                "MANUAL",
            }:
                continue

            evidence_id = str(
                getattr(
                    item,
                    "evidence_id",
                    "",
                )
                or ""
            )

            result = result_map.get(
                evidence_id
            )

            if result is None:
                self._mark_missing(
                    item
                )
                continue

            self._apply_record(
                item,
                result,
            )

        return evidence

    def _apply_record(
        self,
        evidence: Any,
        record: dict[str, Any],
    ) -> None:
        status = str(
            record.get(
                "status",
                "NOT_EXECUTED",
            )
            or "NOT_EXECUTED"
        ).upper()

        original_status = str(
            record.get(
                "original_status",
                status,
            )
            or status
        ).upper()

        observed = bool(
            record.get(
                "observed",
                record.get(
                    "execution_observed",
                    False,
                ),
            )
        )

        synthetic = bool(
            record.get(
                "synthetic",
                False,
            )
        )

        source_tool = str(
            record.get(
                "source_tool",
                "C3_MANUAL_EXECUTION_RECORD",
            )
            or "C3_MANUAL_EXECUTION_RECORD"
        )

        source_upper = (
            source_tool.upper()
        )

        controlled_source = any(
            marker in source_upper
            for marker in {
                "CONTROLLED",
                "SYNTHETIC",
                "FIXTURE",
            }
        )

        # BLOCKED means the test never successfully reached
        # execution completion.
        if original_status == "BLOCKED":
            metadata = dict(
                getattr(
                    evidence,
                    "metadata",
                    None,
                )
                or {}
            )

            metadata.update(
                {
                    "execution_observed":
                        False,

                    "execution_kind":
                        "BLOCKED",

                    "execution_source":
                        source_tool,

                    "original_execution_status":
                        "BLOCKED",

                    "blocked_reason":
                        record.get(
                            "blocked_reason"
                        ),

                    "actual_result":
                        record.get(
                            "actual_result"
                        ),
                }
            )

            if hasattr(
                evidence,
                "metadata",
            ):
                evidence.metadata = (
                    metadata
                )

            if hasattr(
                evidence,
                "execution_status",
            ):
                evidence.execution_status = (
                    "NOT_EXECUTED"
                )

            return

        controlled = (
            synthetic
            or controlled_source
            or not observed
        )

        if controlled:
            (
                ExecutionProvenanceService
                .mark_controlled(
                    evidence,

                    controlled_outcome=(
                        original_status
                    ),

                    source=(
                        source_tool
                    ),

                    execution_id=(
                        record.get(
                            "execution_id"
                        )
                    ),

                    actual_result=(
                        record.get(
                            "actual_result"
                        )
                    ),
                )
            )

            return

        self._validate_observed(
            evidence_id=str(
                getattr(
                    evidence,
                    "evidence_id",
                    "",
                )
            ),

            status=status,

            record=record,
        )

        (
            ExecutionProvenanceService
            .mark_observed(
                evidence,

                status=status,

                source=(
                    source_tool
                ),

                execution_id=(
                    record.get(
                        "execution_id"
                    )
                ),

                executed_at=(
                    record.get(
                        "executed_at"
                    )
                ),

                executed_by=(
                    record.get(
                        "executed_by"
                    )
                ),

                environment=(
                    record.get(
                        "environment"
                    )
                ),

                actual_result=(
                    record.get(
                        "actual_result"
                    )
                ),
            )
        )

    @staticmethod
    def _mark_missing(
        evidence: Any,
    ) -> None:
        metadata = dict(
            getattr(
                evidence,
                "metadata",
                None,
            )
            or {}
        )

        # Do not replace a genuine execution result already
        # provided by another importer.
        if (
            metadata.get(
                "execution_observed"
            )
            is True
        ):
            return

        existing_status = str(
            getattr(
                evidence,
                "execution_status",
                "",
            )
            or ""
        ).upper()

        # Preserve legacy fixture outcome if older evidence
        # definitions stored PASS/FAIL directly.
        if existing_status in {
            "PASS",
            "FAIL",
        }:
            metadata[
                "legacy_controlled_outcome"
            ] = existing_status

        metadata[
            "execution_observed"
        ] = False

        metadata[
            "execution_kind"
        ] = "NOT_EXECUTED"

        if hasattr(
            evidence,
            "metadata",
        ):
            evidence.metadata = (
                metadata
            )

        if hasattr(
            evidence,
            "execution_status",
        ):
            evidence.execution_status = (
                "NOT_EXECUTED"
            )

    def _sanitize_existing(
        self,
        evidence: list[Any],
    ) -> list[Any]:
        """
        Ensure manually defined PASS/FAIL values are not treated
        as real executions unless genuine execution provenance
        exists.
        """

        for item in evidence:
            evidence_type = str(
                getattr(
                    item,
                    "evidence_type",
                    "",
                )
                or ""
            ).upper()

            if evidence_type not in {
                "MANUAL_TEST",
                "MANUAL",
            }:
                continue

            if (
                ExecutionProvenanceService
                .is_observed(
                    item
                )
            ):
                continue

            self._mark_missing(
                item
            )

        return evidence

    @staticmethod
    def _extract_records(
        raw: Any,
    ) -> list[dict[str, Any]]:
        """
        Supports:

        [
            {...}
        ]

        or:

        {
            "results": [...]
        }

        or:

        {
            "executions": [...]
        }

        or:

        {
            "manual_execution_results": [...]
        }
        """

        if isinstance(
            raw,
            list,
        ):
            return raw

        if isinstance(
            raw,
            dict,
        ):
            for key in (
                "results",
                "executions",
                "manual_execution_results",
            ):
                value = raw.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):
                    return value

        raise ValueError(
            (
                "Manual execution results must "
                "be a JSON array or an object "
                "containing a results array."
            )
        )

    def _validate_records(
        self,
        records: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            records,
            list,
        ):
            raise ValueError(
                (
                    "Manual execution records "
                    "must be a list."
                )
            )

        output: list[
            dict[str, Any]
        ] = []

        seen: set[str] = set()

        for index, record in enumerate(
            records,
            start=1,
        ):
            if not isinstance(
                record,
                dict,
            ):
                raise ValueError(
                    (
                        "Manual execution "
                        f"record {index} "
                        "must be an object."
                    )
                )

            evidence_id = str(
                record.get(
                    "evidence_id",
                    "",
                )
                or ""
            ).strip()

            if not evidence_id:
                raise ValueError(
                    (
                        "Manual execution "
                        f"record {index} "
                        "has no evidence_id."
                    )
                )

            if evidence_id in seen:
                raise ValueError(
                    (
                        "Duplicate manual "
                        "execution result for "
                        f"{evidence_id}."
                    )
                )

            seen.add(
                evidence_id
            )

            raw_status = str(
                record.get(
                    "status",
                    "NOT_EXECUTED",
                )
                or "NOT_EXECUTED"
            ).upper()

            if (
                raw_status
                not in self.VALID_STATUSES
            ):
                raise ValueError(
                    (
                        f"{evidence_id}: "
                        "invalid execution "
                        f"status '{raw_status}'."
                    )
                )

            # BLOCKED does not represent a completed execution.
            if raw_status == "BLOCKED":
                normalized_status = (
                    "NOT_EXECUTED"
                )
            else:
                normalized_status = (
                    raw_status
                )

            normalized = dict(
                record
            )

            normalized[
                "evidence_id"
            ] = evidence_id

            normalized[
                "original_status"
            ] = raw_status

            normalized[
                "status"
            ] = normalized_status

            output.append(
                normalized
            )

        return output

    @staticmethod
    def _validate_observed(
        *,
        evidence_id: str,
        status: str,
        record: dict[str, Any],
    ) -> None:
        """
        Real observed manual results require execution provenance.
        """

        required = [
            "execution_id",
            "executed_at",
        ]

        missing = [
            field
            for field
            in required
            if not str(
                record.get(
                    field,
                    "",
                )
                or ""
            ).strip()
        ]

        if missing:
            raise ValueError(
                (
                    f"{evidence_id}: observed "
                    "execution is missing "
                    + ", ".join(
                        missing
                    )
                    + "."
                )
            )

        if (
            status
            in {
                "PASS",
                "FAIL",
            }
            and not str(
                record.get(
                    "actual_result",
                    "",
                )
                or ""
            ).strip()
        ):
            raise ValueError(
                (
                    f"{evidence_id}: observed "
                    f"{status} requires "
                    "actual_result."
                )
            )


def apply_manual_execution_results(
    evidence: list[Any],
    results_path: str | Path,
) -> list[Any]:
    """
    Backward-compatible helper.
    """

    return (
        ManualExecutionService(
            results_path=results_path
        )
        .apply(
            evidence
        )
    )