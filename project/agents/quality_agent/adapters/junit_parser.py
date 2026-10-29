from __future__ import annotations

import re
from pathlib import Path

from agents.quality_agent.schemas import (
    TestArtifact,
)


class JUnitParser:
    TEST_METHOD_PATTERN = re.compile(
        r"@(?:Test|ParameterizedTest)"
        r"(?:\([^)]*\))?"
        r"(?:\s*[\r\n]+\s*"
        r"@[^\r\n]+)*"
        r"\s*[\r\n]+\s*"
        r"(?:public|protected|private)?\s*"
        r"(?:static\s+)?"
        r"(?:void|[\w<>\[\],.? ]+)\s+"
        r"(\w+)\s*"
        r"\([^)]*\)"
        r"(?:\s+throws\s+[^{]+)?"
        r"\s*\{",
        re.MULTILINE,
    )

    NESTED_CLASS_PATTERN = re.compile(
        r"@Nested\s*[\r\n]+\s*"
        r"(?:public|protected|private)?\s*"
        r"class\s+(\w+)\s*\{",
        re.MULTILINE,
    )

    ASSERTION_PATTERN = re.compile(
        r"\b("
        r"assert\w*"
        r"|assertThat"
        r"|andExpect"
        r"|verify"
        r"|expect"
        r")\b",
        re.IGNORECASE,
    )

    def parse_directory(
        self,
        root: Path,
    ) -> list[TestArtifact]:

        if not root.exists():
            return []

        evidence: list[
            TestArtifact
        ] = []

        for path in root.rglob(
            "*.java"
        ):
            evidence.extend(
                self.parse_file(
                    path
                )
            )

        return evidence

    def parse_file(
        self,
        path: Path,
    ) -> list[TestArtifact]:

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        package_match = re.search(
            r"^\s*package\s+"
            r"([\w.]+)\s*;",
            text,
            re.MULTILINE,
        )

        package_name = (
            package_match.group(1)
            if package_match
            else None
        )

        outer_class = path.stem

        nested_ranges = (
            self._nested_class_ranges(
                text
            )
        )

        evidence: list[
            TestArtifact
        ] = []

        for match in (
            self
            .TEST_METHOD_PATTERN
            .finditer(text)
        ):
            method_name = (
                match.group(1)
            )

            body = (
                self._extract_block(
                    text,
                    match.end() - 1,
                )
            )

            nested_names = [
                name
                for (
                    start,
                    end,
                    name,
                )
                in nested_ranges
                if (
                    start
                    < match.start()
                    < end
                )
            ]

            class_suffix = (
                outer_class
            )

            if nested_names:
                class_suffix += (
                    "$"
                    + "$".join(
                        nested_names
                    )
                )

            full_class_name = (
                f"{package_name}."
                f"{class_suffix}"
                if package_name
                else class_suffix
            )

            assertions = [
                line.strip()
                for line
                in body.splitlines()
                if (
                    self
                    .ASSERTION_PATTERN
                    .search(line)
                )
            ]

            annotations = (
                self
                ._annotations_before(
                    text,
                    match.start(),
                )
            )

            evidence.append(
                TestArtifact(
                    artifact_id=(
                        f"JUNIT-"
                        f"{class_suffix}-"
                        f"{method_name}"
                    ),
                    artifact_type=(
                        "AUTOMATED_TEST"
                    ),
                    title=(
                        self._humanize(
                            method_name
                        )
                    ),
                    description=(
                        body[:5000]
                    ),
                    assertions=(
                        assertions
                    ),
                    class_name=(
                        full_class_name
                    ),
                    method_name=(
                        method_name
                    ),
                    source_path=str(
                        path
                    ),
                    source_tool=(
                        "JUNIT_SOURCE"
                    ),
                    source_version=(
                        "JUnit Jupiter"
                    ),
                    raw_reference=(
                        f"{full_class_name}"
                        f"#{method_name}"
                    ),
                    annotations=(
                        annotations
                    ),
                )
            )

        return evidence

    def _nested_class_ranges(
        self,
        text: str,
    ) -> list[
        tuple[int, int, str]
    ]:

        ranges: list[
            tuple[int, int, str]
        ] = []

        for match in (
            self
            .NESTED_CLASS_PATTERN
            .finditer(text)
        ):
            opening = text.find(
                "{",
                match.start(),
                match.end(),
            )

            if opening < 0:
                continue

            closing = (
                self
                ._find_closing_brace(
                    text,
                    opening,
                )
            )

            ranges.append(
                (
                    match.start(),
                    closing,
                    match.group(1),
                )
            )

        return ranges

    @staticmethod
    def _extract_block(
        text: str,
        opening_brace_index: int,
    ) -> str:

        closing = (
            JUnitParser
            ._find_closing_brace(
                text,
                opening_brace_index,
            )
        )

        return text[
            opening_brace_index + 1:
            closing
        ].strip()

    @staticmethod
    def _find_closing_brace(
        text: str,
        opening_brace_index: int,
    ) -> int:

        depth = 0

        in_string = False
        escape = False
        quote = ""

        for index in range(
            opening_brace_index,
            len(text),
        ):
            char = text[
                index
            ]

            if in_string:
                if escape:
                    escape = False

                elif char == "\\":
                    escape = True

                elif char == quote:
                    in_string = False

                continue

            if char in {
                '"',
                "'",
            }:
                in_string = True
                quote = char

            elif char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    return index

        return len(text) - 1

    @staticmethod
    def _annotations_before(
        text: str,
        method_start: int,
    ) -> list[str]:

        window = text[
            max(
                0,
                method_start - 500,
            ):
            method_start
        ]

        lines = (
            window.splitlines()
        )

        annotations: list[str] = []

        for line in reversed(
            lines
        ):
            stripped = (
                line.strip()
            )

            if stripped.startswith(
                "@"
            ):
                annotations.append(
                    stripped
                )
                continue

            if not stripped:
                continue

            break

        return list(
            reversed(
                annotations
            )
        )

    @staticmethod
    def _humanize(
        method_name: str,
    ) -> str:

        value = re.sub(
            r"([a-z0-9])([A-Z])",
            r"\1 \2",
            method_name,
        )

        return (
            value
            .replace(
                "_",
                " ",
            )
            .strip()
        )