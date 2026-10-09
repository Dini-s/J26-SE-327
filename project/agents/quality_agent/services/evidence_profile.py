from __future__ import annotations

import re

from agents.quality_agent.schemas import (
    ExpectedEvidenceProfile,
    RequirementRecord,
    RequirementValidationUnit,
)


class EvidenceProfileGenerator:
    def generate(
        self,
        requirements: list[RequirementRecord],
        rvus: list[RequirementValidationUnit],
    ) -> list[ExpectedEvidenceProfile]:

        requirement_map = {
            requirement.requirement_id:
            requirement
            for requirement
            in requirements
        }

        profiles: list[
            ExpectedEvidenceProfile
        ] = []

        for rvu in rvus:
            requirement = (
                requirement_map[
                    rvu.requirement_id
                ]
            )

            if (
                requirement.type.upper()
                == "NON_FUNCTIONAL"
            ):
                profile = (
                    self
                    ._build_nfr_profile(
                        requirement,
                        rvu,
                    )
                )

            else:
                profile = (
                    self
                    ._build_functional_profile(
                        requirement,
                        rvu,
                    )
                )

            profiles.append(
                profile
            )

        return profiles

    def _build_functional_profile(
        self,
        requirement:
        RequirementRecord,
        rvu:
        RequirementValidationUnit,
    ) -> ExpectedEvidenceProfile:

        scenario_map = {
            "POSITIVE": [
                "POSITIVE"
            ],
            "NEGATIVE": [
                "NEGATIVE"
            ],
            "BOUNDARY": [
                "BOUNDARY"
            ],
            "STATE": [
                "STATE_TRANSITION"
            ],
        }

        assertion_map = {
            "POSITIVE": (
                "Assert the required successful "
                "behavior or resulting state."
            ),
            "NEGATIVE": (
                "Assert the invalid or prohibited "
                "condition is rejected and no "
                "invalid state is persisted."
            ),
            "BOUNDARY": (
                "Assert behavior at and around "
                "the specified boundary or "
                "threshold."
            ),
            "STATE": (
                "Assert the expected state "
                "transition and resulting state."
            ),
        }

        return ExpectedEvidenceProfile(
            profile_id=(
                f"EP-{rvu.rvu_id}"
            ),
            rvu_id=rvu.rvu_id,
            requirement_id=(
                rvu.requirement_id
            ),
            ac_id=rvu.ac_id,
            requirement_type=(
                requirement.type
            ),
            requirement_subtype=(
                requirement.subtype
            ),
            evidence_type=(
                "FUNCTIONAL_TEST_EVIDENCE"
            ),
            required_scenarios=(
                scenario_map.get(
                    rvu.behavior_type,
                    ["FUNCTIONAL"],
                )
            ),
            preconditions=[
                (
                    "The system is in a valid "
                    "state for exercising the RVU."
                )
            ],
            inputs=[
                (
                    "Input data capable of "
                    "triggering the behavior "
                    "described by the RVU."
                )
            ],
            expected_outcomes=[
                rvu.atomic_text
            ],
            required_assertions=[
                assertion_map.get(
                    rvu.behavior_type,
                    (
                        "Assert the behavior "
                        "described by the RVU "
                        "and the resulting "
                        "system state."
                    ),
                )
            ],
            support_status="SUPPORTED",
            support_reason=(
                "Functional evidence strategy "
                "is supported by the current "
                "prototype."
            ),
        )

    def _build_nfr_profile(
        self,
        requirement:
        RequirementRecord,
        rvu:
        RequirementValidationUnit,
    ) -> ExpectedEvidenceProfile:

        subtype = (
            requirement.subtype.upper()
        )

        if subtype != "PERFORMANCE":
            return ExpectedEvidenceProfile(
                profile_id=(
                    f"EP-{rvu.rvu_id}"
                ),
                rvu_id=rvu.rvu_id,
                requirement_id=(
                    rvu.requirement_id
                ),
                ac_id=rvu.ac_id,
                requirement_type=(
                    requirement.type
                ),
                requirement_subtype=(
                    requirement.subtype
                ),
                evidence_type=(
                    "SPECIALIZED_NFR_EVIDENCE"
                ),
                required_scenarios=[
                    subtype
                ],
                expected_outcomes=[
                    rvu.atomic_text
                ],
                support_status=(
                    "UNSUPPORTED"
                ),
                support_reason=(
                    f"{subtype} requires "
                    f"a specialized evidence "
                    f"adapter/rule catalogue "
                    f"not enabled in the "
                    f"current prototype."
                ),
            )

        metric = (
            self._metric(
                rvu.atomic_text
            )
        )

        percentile = (
            self._percentile(
                rvu.atomic_text
            )
        )

        (
            operator,
            threshold,
            unit,
        ) = self._threshold(
            rvu.atomic_text
        )

        load = self._load(
            rvu.atomic_text
        )

        duration = (
            self._duration_seconds(
                rvu.atomic_text
            )
        )

        if (
            metric
            == "unhandled_failures"
        ):
            operator = "=="
            threshold = 0.0
            unit = "count"

        elif (
            metric
            == "test_duration"
            and duration
            is not None
        ):
            operator = ">="
            threshold = float(
                duration
            )
            unit = "seconds"

        support_status = (
            "SUPPORTED"
        )

        support_reason = (
            "Measurable performance "
            "evidence can be evaluated "
            "by the current adapter."
        )

        if metric is None:
            support_status = (
                "REVIEW_REQUIRED"
            )

            support_reason = (
                "The requirement is classified "
                "as PERFORMANCE but this RVU "
                "does not expose a supported "
                "measurable performance metric."
            )

        return ExpectedEvidenceProfile(
            profile_id=(
                f"EP-{rvu.rvu_id}"
            ),
            rvu_id=rvu.rvu_id,
            requirement_id=(
                rvu.requirement_id
            ),
            ac_id=rvu.ac_id,
            requirement_type=(
                requirement.type
            ),
            requirement_subtype=(
                requirement.subtype
            ),
            evidence_type=(
                "PERFORMANCE_TEST_EVIDENCE"
            ),
            required_scenarios=[
                "PERFORMANCE"
            ],
            preconditions=[
                (
                    "The target operation "
                    "and test environment "
                    "are available."
                )
            ],
            inputs=[
                (
                    "A workload/configuration "
                    "matching the measurable "
                    "RVU conditions."
                )
            ],
            expected_outcomes=[
                rvu.atomic_text
            ],
            required_assertions=[
                (
                    "Compare the measured result "
                    "with the required metric, "
                    "threshold, workload, "
                    "duration and scope."
                )
            ],
            metric=metric,
            percentile=percentile,
            operator=operator,
            threshold=threshold,
            unit=unit,
            load=load,
            duration_seconds=(
                duration
            ),
            scope=requirement.title,
            support_status=(
                support_status
            ),
            support_reason=(
                support_reason
            ),
        )

    @staticmethod
    def _metric(
        text: str,
    ) -> str | None:

        lower = text.lower()

        if "response time" in lower:
            return "response_time"

        if (
            "failed-request rate"
            in lower
            or "error rate"
            in lower
        ):
            return "error_rate"

        if (
            "without an unhandled "
            "application failure"
            in lower
        ):
            return (
                "unhandled_failures"
            )

        if (
            "workload shall run"
            in lower
            or "test shall run"
            in lower
        ):
            return "test_duration"

        return None

    @staticmethod
    def _percentile(
        text: str,
    ) -> str | None:

        match = re.search(
            r"\b(p\d{2})\b",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        return (
            match.group(1).lower()
        )

    @staticmethod
    def _threshold(
        text: str,
    ) -> tuple[
        str | None,
        float | None,
        str | None,
    ]:

        patterns = [
            (
                "<",
                (
                    r"\bbelow\s+"
                    r"(\d+(?:\.\d+)?)\s*"
                    r"(milliseconds?|"
                    r"seconds?|percent|%)"
                ),
            ),
            (
                ">=",
                (
                    r"\bat\s+least\s+"
                    r"(\d+(?:\.\d+)?)\s*"
                    r"(milliseconds?|"
                    r"seconds?|percent|%)"
                ),
            ),
            (
                ">",
                (
                    r"\bgreater\s+than\s+"
                    r"(\d+(?:\.\d+)?)\s*"
                    r"(milliseconds?|"
                    r"seconds?|percent|%)"
                ),
            ),
            (
                "==",
                (
                    r"\bexactly\s+"
                    r"(\d+(?:\.\d+)?)\s*"
                    r"(milliseconds?|"
                    r"seconds?|percent|%)"
                ),
            ),
        ]

        for operator, pattern in (
            patterns
        ):
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                return (
                    operator,
                    float(
                        match.group(1)
                    ),
                    match
                    .group(2)
                    .lower(),
                )

        return None, None, None

    @staticmethod
    def _load(
        text: str,
    ) -> int | None:

        match = re.search(
            r"\b(\d+)\s+"
            r"concurrent\s+users?\b",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        return int(
            match.group(1)
        )

    @staticmethod
    def _duration_seconds(
        text: str,
    ) -> int | None:

        match = re.search(
            r"\b(?:for|during)\s+"
            r"(?:the\s+)?"
            r"(\d+)[-\s]"
            r"(second|minute|hour)s?\b",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        value = int(
            match.group(1)
        )

        multipliers = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
        }

        return (
            value
            * multipliers[
                match.group(2)
                .lower()
            ]
        )