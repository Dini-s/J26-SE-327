from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from agents.quality_agent.schemas import (
    ExecutionResult,
)


class SurefireParser:
    def parse_directory(
        self,
        root: Path,
    ) -> list[ExecutionResult]:

        if not root.exists():
            return []

        results: list[
            ExecutionResult
        ] = []

        for path in root.glob(
            "TEST-*.xml"
        ):
            results.extend(
                self.parse_file(
                    path
                )
            )

        return results

    def parse_file(
        self,
        path: Path,
    ) -> list[ExecutionResult]:

        try:
            root = (
                ET.parse(
                    path
                )
                .getroot()
            )

        except ET.ParseError:
            return []

        results: list[
            ExecutionResult
        ] = []

        run_id = path.stem

        for testcase in root.iter(
            "testcase"
        ):
            class_name = (
                testcase.get(
                    "classname",
                    "",
                )
            )

            raw_method_name = (
                testcase.get(
                    "name",
                    "",
                )
            )

            method_name = (
                self
                ._normalize_method_name(
                    raw_method_name
                )
            )

            try:
                duration_ms = (
                    float(
                        testcase.get(
                            "time",
                            "0",
                        )
                        or 0
                    )
                    * 1000
                )

            except ValueError:
                duration_ms = None

            status = "PASS"
            error_message = None

            failure = (
                testcase.find(
                    "failure"
                )
            )

            error = (
                testcase.find(
                    "error"
                )
            )

            skipped = (
                testcase.find(
                    "skipped"
                )
            )

            if failure is not None:
                status = "FAIL"

                error_message = (
                    failure.get(
                        "message"
                    )
                    or failure.text
                )

            elif error is not None:
                status = "ERROR"

                error_message = (
                    error.get(
                        "message"
                    )
                    or error.text
                )

            elif skipped is not None:
                status = "SKIPPED"

            results.append(
                ExecutionResult(
                    execution_id=(
                        f"SUREFIRE-"
                        f"{class_name.split('.')[-1]}"
                        f"-{method_name}"
                    ),
                    class_name=(
                        class_name
                    ),
                    method_name=(
                        method_name
                    ),
                    status=status,
                    duration_ms=(
                        duration_ms
                    ),
                    source_path=str(
                        path
                    ),
                    source_tool=(
                        "MAVEN_SUREFIRE"
                    ),
                    run_id=run_id,
                    error_message=(
                        error_message
                    ),
                )
            )

        return results

    @staticmethod
    def _normalize_method_name(
        value: str,
    ) -> str:

        value = value.split(
            "[",
            1,
        )[0]

        value = value.split(
            "(",
            1,
        )[0]

        return value.strip()