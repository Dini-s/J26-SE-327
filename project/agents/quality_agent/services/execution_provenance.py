from __future__ import annotations

from typing import Any


class ExecutionProvenanceService:
    """
    Central policy for execution provenance.

    Important distinction:

        synthetic/controlled result != real execution result

    Controlled fixtures may contain expected PASS/FAIL outcomes
    for exercising the C3 pipeline, but they must never count as
    execution-confirmed validation.

    Real execution can come from:
    - Maven Surefire / JUnit
    - Newman / Postman
    - Playwright / Selenium / Cypress
    - JMeter / k6
    - CI execution reports
    - genuine manual execution records
    """

    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    NOT_EXECUTED = "NOT_EXECUTED"
    ERROR = "ERROR"

    CONTROLLED_MARKERS = {
        "CONTROLLED",
        "SYNTHETIC",
        "FIXTURE",
    }

    @staticmethod
    def metadata(
        evidence: Any,
    ) -> dict[str, Any]:
        value = getattr(
            evidence,
            "metadata",
            None,
        )

        if isinstance(
            value,
            dict,
        ):
            return value

        return {}

    @classmethod
    def is_controlled(
        cls,
        evidence: Any,
    ) -> bool:
        metadata = cls.metadata(
            evidence
        )

        if (
            metadata.get(
                "execution_observed"
            )
            is False
        ):
            return True

        if bool(
            getattr(
                evidence,
                "synthetic",
                False,
            )
        ):
            return True

        execution_kind = str(
            metadata.get(
                "execution_kind",
                "",
            )
            or ""
        ).upper()

        source_tool = str(
            getattr(
                evidence,
                "source_tool",
                "",
            )
            or ""
        ).upper()

        execution_source = str(
            metadata.get(
                "execution_source",
                "",
            )
            or ""
        ).upper()

        combined = (
            execution_kind
            + " "
            + source_tool
            + " "
            + execution_source
        )

        return any(
            marker in combined
            for marker
            in cls.CONTROLLED_MARKERS
        )

    @classmethod
    def is_observed(
        cls,
        evidence: Any,
    ) -> bool:
        metadata = cls.metadata(
            evidence
        )

        # Explicit controlled/synthetic provenance
        # always wins.
        if cls.is_controlled(
            evidence
        ):
            return False

        # Explicit observed provenance.
        if (
            metadata.get(
                "execution_observed"
            )
            is True
        ):
            return True

        if (
            metadata.get(
                "observed"
            )
            is True
        ):
            return True

        execution_kind = str(
            metadata.get(
                "execution_kind",
                "",
            )
            or ""
        ).upper()

        if execution_kind in {
            "OBSERVED",
            "REAL",
            "TOOL_EXECUTION",
            "MANUAL_OBSERVED",
        }:
            return True

        evidence_type = str(
            getattr(
                evidence,
                "evidence_type",
                "",
            )
            or ""
        ).upper()

        status = str(
            getattr(
                evidence,
                "execution_status",
                "",
            )
            or ""
        ).upper()

        run_id = getattr(
            evidence,
            "execution_run_id",
            None,
        )

        # Real automated execution report.
        if (
            evidence_type
            == "AUTOMATED_TEST"
            and run_id
            and status
            in {
                cls.PASS,
                cls.FAIL,
                cls.SKIPPED,
            }
        ):
            return True

        # Real performance execution report.
        if (
            evidence_type
            == "PERFORMANCE_EVIDENCE"
            and run_id
            and status
            in {
                cls.PASS,
                cls.FAIL,
            }
        ):
            return True

        # Manual evidence must explicitly declare
        # that a real execution was observed.
        return False

    @classmethod
    def is_qualifying_pass(
        cls,
        evidence: Any,
    ) -> bool:
        status = str(
            getattr(
                evidence,
                "execution_status",
                "",
            )
            or ""
        ).upper()

        return (
            status == cls.PASS
            and cls.is_observed(
                evidence
            )
        )

    @classmethod
    def mark_controlled(
        cls,
        evidence: Any,
        *,
        controlled_outcome: str | None,
        source: str,
        execution_id: str | None = None,
        actual_result: str | None = None,
    ) -> Any:
        """
        Preserve the synthetic outcome for research/debugging,
        but expose the real execution status as NOT_EXECUTED.
        """

        metadata = dict(
            cls.metadata(
                evidence
            )
        )

        normalized_outcome = (
            str(
                controlled_outcome
                or ""
            ).upper()
            or None
        )

        metadata.update(
            {
                "execution_observed":
                    False,

                "execution_kind":
                    "CONTROLLED_FIXTURE",

                "execution_source":
                    source,

                "controlled_outcome":
                    normalized_outcome,

                "controlled_execution_id":
                    execution_id,

                "controlled_actual_result":
                    actual_result,
            }
        )

        if hasattr(
            evidence,
            "metadata",
        ):
            evidence.metadata = (
                metadata
            )

        # This is the important part:
        # a synthetic PASS is NOT a real execution PASS.
        if hasattr(
            evidence,
            "execution_status",
        ):
            evidence.execution_status = (
                cls.NOT_EXECUTED
            )

        return evidence

    @classmethod
    def mark_observed(
        cls,
        evidence: Any,
        *,
        status: str,
        source: str,
        execution_id: str | None = None,
        executed_at: str | None = None,
        executed_by: str | None = None,
        environment: str | None = None,
        actual_result: str | None = None,
    ) -> Any:
        metadata = dict(
            cls.metadata(
                evidence
            )
        )

        normalized_status = str(
            status
            or cls.NOT_EXECUTED
        ).upper()

        metadata.update(
            {
                "execution_observed":
                    True,

                "execution_kind":
                    "OBSERVED",

                "execution_source":
                    source,

                "executed_at":
                    executed_at,

                "executed_by":
                    executed_by,

                "execution_environment":
                    environment,

                "actual_result":
                    actual_result,
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
                normalized_status
            )

        if (
            execution_id
            and hasattr(
                evidence,
                "execution_run_id",
            )
        ):
            evidence.execution_run_id = (
                execution_id
            )

        return evidence

    @classmethod
    def display_state(
        cls,
        evidence: Any,
    ) -> dict[str, Any]:
        """
        User-facing execution interpretation.
        """

        status = str(
            getattr(
                evidence,
                "execution_status",
                cls.NOT_EXECUTED,
            )
            or cls.NOT_EXECUTED
        ).upper()

        observed = cls.is_observed(
            evidence
        )

        if (
            status == cls.PASS
            and observed
        ):
            return {
                "status":
                    cls.PASS,

                "observed":
                    True,

                "label":
                    "Observed PASS",

                "detail":
                    "Execution confirmed",
            }

        if (
            status == cls.FAIL
            and observed
        ):
            return {
                "status":
                    cls.FAIL,

                "observed":
                    True,

                "label":
                    "Observed FAIL",

                "detail":
                    "Execution confirmed",
            }

        if status == cls.SKIPPED:
            return {
                "status":
                    cls.SKIPPED,

                "observed":
                    observed,

                "label":
                    "Skipped",

                "detail":
                    (
                        "Execution not completed"
                    ),
            }

        if status == cls.ERROR:
            return {
                "status":
                    cls.ERROR,

                "observed":
                    observed,

                "label":
                    "Execution Error",

                "detail":
                    "Execution could not complete",
            }

        metadata = cls.metadata(
            evidence
        )

        controlled_outcome = (
            metadata.get(
                "controlled_outcome"
            )
        )

        detail = (
            "Real execution required"
        )

        if controlled_outcome:
            detail = (
                "Synthetic fixture available; "
                "real execution required"
            )

        return {
            "status":
                cls.NOT_EXECUTED,

            "observed":
                False,

            "label":
                "Not Executed",

            "detail":
                detail,
        }