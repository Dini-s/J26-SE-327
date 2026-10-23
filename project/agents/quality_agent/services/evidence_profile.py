from __future__ import annotations

import re

from agents.quality_agent.schemas import (
    ExpectedEvidenceProfile,
    RequirementRecord,
    RequirementValidationUnit,
)


class EvidenceProfileGenerator:
    """
    Generates an Expected Evidence Profile for every RVU.

    The profile describes what evidence would be required
    to validate the RVU before the currently available
    evidence is inspected.

    Functional requirements are supported directly.

    Performance NFRs are supported when a measurable
    metric can be derived.

    Other NFR categories remain explicitly unsupported
    for automatic adequacy assessment until a dedicated
    evidence rule is implemented.
    """

    PERFORMANCE_SUBTYPE = "PERFORMANCE"

    SUPPORTED_PERFORMANCE_METRICS = {
        "response_time",
        "error_rate",
        "unhandled_failures",
    }

    def generate(
        self,
        requirements: list[RequirementRecord],
        rvus: list[RequirementValidationUnit],
    ) -> list[ExpectedEvidenceProfile]:

        requirement_map = {
            requirement.requirement_id:
            requirement
            for requirement in requirements
        }

        profiles: list[
            ExpectedEvidenceProfile
        ] = []

        for rvu in rvus:
            requirement = requirement_map.get(
                rvu.requirement_id
            )

            if requirement is None:
                raise ValueError(
                    (
                        "Requirement not found "
                        f"for RVU {rvu.rvu_id}"
                    )
                )

            profile = self._build_profile(
                requirement=requirement,
                rvu=rvu,
            )

            profiles.append(profile)

        return profiles

    def _build_profile(
        self,
        *,
        requirement: RequirementRecord,
        rvu: RequirementValidationUnit,
    ) -> ExpectedEvidenceProfile:

        requirement_type = (
            requirement.type.upper()
        )

        requirement_subtype = (
            requirement.subtype.upper()
        )

        if requirement_type == "FUNCTIONAL":
            return self._functional_profile(
                requirement=requirement,
                rvu=rvu,
            )

        if (
            requirement_type
            == "NON_FUNCTIONAL"
            and requirement_subtype
            == self.PERFORMANCE_SUBTYPE
        ):
            return self._performance_profile(
                requirement=requirement,
                rvu=rvu,
            )

        return self._unsupported_nfr_profile(
            requirement=requirement,
            rvu=rvu,
        )

    def _functional_profile(
        self,
        *,
        requirement: RequirementRecord,
        rvu: RequirementValidationUnit,
    ) -> ExpectedEvidenceProfile:

        behavior = (
            rvu.behavior_type.upper()
        )

        scenarios: list[str] = []

        if behavior == "NEGATIVE":
            scenarios.append(
                "Negative validation scenario"
            )

        elif behavior == "BOUNDARY":
            scenarios.append(
                "Boundary-value validation scenario"
            )

        elif behavior in {
            "STATE",
            "STATE_TRANSITION",
        }:
            scenarios.append(
                "State-transition validation scenario"
            )

        else:
            scenarios.append(
                "Positive functional validation scenario"
            )

        preconditions = self._functional_preconditions(
            rvu.atomic_text
        )

        inputs = self._functional_inputs(
            rvu.atomic_text
        )

        expected_outcomes = [
            rvu.atomic_text
        ]

        assertions = [
            (
                "Assert the observable outcome "
                "defined by the RVU."
            )
        ]

        if behavior == "NEGATIVE":
            assertions.append(
                (
                    "Assert that the invalid or "
                    "disallowed behavior is rejected."
                )
            )

        elif behavior == "BOUNDARY":
            assertions.append(
                (
                    "Assert behavior at the exact "
                    "boundary and immediately around it."
                )
            )

        elif behavior in {
            "STATE",
            "STATE_TRANSITION",
        }:
            assertions.append(
                (
                    "Assert the expected state "
                    "after the operation."
                )
            )

        return ExpectedEvidenceProfile(
            profile_id=(
                f"EEP::{rvu.rvu_id}"
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
                "FUNCTIONAL_TEST"
            ),
            required_scenarios=scenarios,
            preconditions=preconditions,
            inputs=inputs,
            expected_outcomes=(
                expected_outcomes
            ),
            required_assertions=(
                assertions
            ),
            support_status="SUPPORTED",
            support_reason=None,
            generation_method=(
                "DETERMINISTIC_EXPECTED_EVIDENCE_V2"
            ),
        )

    def _performance_profile(
        self,
        *,
        requirement: RequirementRecord,
        rvu: RequirementValidationUnit,
    ) -> ExpectedEvidenceProfile:

        text = " ".join(
            [
                requirement.text,
                rvu.atomic_text,
                " ".join(
                    rvu.constraints
                ),
            ]
        )

        metric = self._detect_metric(
            text
        )

        percentile = (
            self._extract_percentile(
                text
            )
        )

        operator = (
            self._extract_operator(
                text
            )
        )

        threshold, unit = (
            self._extract_threshold(
                text=text,
                metric=metric,
            )
        )

        load = self._extract_load(
            text
        )

        duration_seconds = (
            self._extract_duration_seconds(
                text
            )
        )

        scope = self._extract_scope(
            requirement=requirement,
            text=text,
        )

        required_scenarios = [
            (
                "Execute the required "
                "performance scenario under "
                "the stated workload."
            )
        ]

        expected_outcomes = [
            rvu.atomic_text
        ]

        required_assertions = [
            (
                "Compare the measured metric "
                "against the requirement threshold."
            )
        ]

        if percentile:
            required_assertions.append(
                (
                    f"Evaluate the "
                    f"{percentile} percentile."
                )
            )

        if load is not None:
            required_scenarios.append(
                (
                    f"Apply at least {load} "
                    "concurrent users."
                )
            )

        if duration_seconds is not None:
            required_scenarios.append(
                (
                    "Maintain the workload for "
                    f"at least "
                    f"{duration_seconds} seconds."
                )
            )

        supported = (
            metric
            in self
            .SUPPORTED_PERFORMANCE_METRICS
        )

        if supported:
            support_status = (
                "SUPPORTED"
            )

            support_reason = None

        else:
            support_status = (
                "REVIEW_REQUIRED"
            )

            support_reason = (
                "The performance RVU does not "
                "contain a metric currently "
                "supported by the deterministic "
                "performance adequacy rules."
            )

        return ExpectedEvidenceProfile(
            profile_id=(
                f"EEP::{rvu.rvu_id}"
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
                "PERFORMANCE_EVIDENCE"
            ),
            required_scenarios=(
                required_scenarios
            ),
            preconditions=[],
            inputs=[],
            expected_outcomes=(
                expected_outcomes
            ),
            required_assertions=(
                required_assertions
            ),
            metric=metric,
            percentile=percentile,
            operator=operator,
            threshold=threshold,
            unit=unit,
            load=load,
            duration_seconds=(
                duration_seconds
            ),
            scope=scope,
            support_status=(
                support_status
            ),
            support_reason=(
                support_reason
            ),
            generation_method=(
                "DETERMINISTIC_EXPECTED_EVIDENCE_V2"
            ),
        )

    def _unsupported_nfr_profile(
        self,
        *,
        requirement: RequirementRecord,
        rvu: RequirementValidationUnit,
    ) -> ExpectedEvidenceProfile:

        subtype = (
            requirement.subtype.upper()
        )

        evidence_guidance = {
            "SECURITY": (
                "Security test evidence, "
                "SAST/DAST or security scan evidence."
            ),
            "SECURITY_BEHAVIOR": (
                "Security-focused validation evidence."
            ),
            "RELIABILITY": (
                "Sustained workload, failure and "
                "recovery evidence."
            ),
            "AVAILABILITY": (
                "Availability telemetry and "
                "measurement-period evidence."
            ),
            "SCALABILITY": (
                "Load, throughput, latency and "
                "resource-utilization evidence."
            ),
            "ACCESSIBILITY": (
                "WCAG or automated accessibility "
                "audit evidence."
            ),
            "MAINTAINABILITY": (
                "Coverage, complexity or static "
                "analysis evidence."
            ),
            "USABILITY": (
                "Expert review or usability-study "
                "evidence."
            ),
            "AUDIT": (
                "Audit-log and trace evidence."
            ),
            "AUTHORIZATION": (
                "Authorization and access-control "
                "validation evidence."
            ),
            "DATA_INTEGRITY": (
                "Integrity, persistence and "
                "consistency validation evidence."
            ),
        }

        guidance = evidence_guidance.get(
            subtype,
            (
                "Specialized non-functional "
                "evidence is required."
            ),
        )

        return ExpectedEvidenceProfile(
            profile_id=(
                f"EEP::{rvu.rvu_id}"
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
                guidance
            ],
            preconditions=[],
            inputs=[],
            expected_outcomes=[
                rvu.atomic_text
            ],
            required_assertions=[
                (
                    "Provide measurable evidence "
                    "for the NFR condition."
                )
            ],
            support_status="UNSUPPORTED",
            support_reason=(
                (
                    f"Automatic adequacy assessment "
                    f"for {requirement.subtype} "
                    "evidence is not implemented. "
                    "The requirement is therefore "
                    "preserved as explicitly "
                    "unsupported rather than "
                    "receiving an inferred decision."
                )
            ),
            generation_method=(
                "DETERMINISTIC_EXPECTED_EVIDENCE_V2"
            ),
        )

    def _detect_metric(
        self,
        text: str,
    ) -> str | None:

        lower = text.lower()

        if (
            "response time" in lower
            or "latency" in lower
        ):
            return "response_time"

        if (
            "error rate" in lower
            or "failure rate" in lower
            or "failed-request rate"
            in lower
            or "failed request rate"
            in lower
        ):
            return "error_rate"

        if (
            "unhandled failure" in lower
            or "unhandled failures"
            in lower
            or "unhandled application failure"
            in lower
        ):
            return "unhandled_failures"

        return None

    @staticmethod
    def _extract_percentile(
        text: str,
    ) -> str | None:

        match = re.search(
            r"\bp\s*(\d{2})\b",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return (
            f"p{match.group(1)}"
        )

    @staticmethod
    def _extract_operator(
        text: str,
    ) -> str | None:

        lower = text.lower()

        if any(
            phrase in lower
            for phrase in [
                "less than or equal",
                "at most",
                "no more than",
                "not exceed",
            ]
        ):
            return "<="

        if any(
            phrase in lower
            for phrase in [
                "below",
                "less than",
                "under",
            ]
        ):
            return "<"

        if any(
            phrase in lower
            for phrase in [
                "greater than or equal",
                "at least",
                "no less than",
            ]
        ):
            return ">="

        if any(
            phrase in lower
            for phrase in [
                "greater than",
                "more than",
                "above",
            ]
        ):
            return ">"

        if (
            "without an unhandled"
            in lower
            or "without unhandled"
            in lower
        ):
            return "=="

        return None

    def _extract_threshold(
        self,
        *,
        text: str,
        metric: str | None,
    ) -> tuple[
        float | None,
        str | None,
    ]:

        lower = text.lower()

        if metric == "response_time":
            match = re.search(
                (
                    r"(?:below|under|less than|"
                    r"at most|no more than|"
                    r"not exceed(?:ing)?)"
                    r"\s*"
                    r"(\d+(?:\.\d+)?)"
                    r"\s*"
                    r"(milliseconds?|ms|"
                    r"seconds?|secs?|s)"
                ),
                lower,
            )

            if match:
                value = float(
                    match.group(1)
                )

                unit = (
                    self._normalize_unit(
                        match.group(2)
                    )
                )

                return value, unit

        if metric == "error_rate":
            match = re.search(
                (
                    r"(?:below|under|less than|"
                    r"at most|no more than)"
                    r"\s*"
                    r"(\d+(?:\.\d+)?)"
                    r"\s*"
                    r"(percent|%)"
                ),
                lower,
            )

            if match:
                return (
                    float(
                        match.group(1)
                    ),
                    "percent",
                )

        if (
            metric
            == "unhandled_failures"
        ):
            if (
                "without unhandled"
                in lower
                or (
                    "no unhandled"
                    in lower
                )
            ):
                return (
                    0.0,
                    "count",
                )

        return None, None

    @staticmethod
    def _extract_load(
        text: str,
    ) -> int | None:

        match = re.search(
            (
                r"\b(\d+)\s+"
                r"concurrent\s+users?\b"
            ),
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return int(
            match.group(1)
        )

    @staticmethod
    def _extract_duration_seconds(
        text: str,
    ) -> int | None:

        candidates: list[
            tuple[int, int]
        ] = []

        patterns = [
            (
                r"\b(\d+)\s*"
                r"(seconds?|secs?|s)\b",
                1,
            ),
            (
                r"\b(\d+)\s*"
                r"(minutes?|mins?|min)\b",
                60,
            ),
            (
                r"\b(\d+)\s*"
                r"(hours?|hrs?|hr)\b",
                3600,
            ),
        ]

        for pattern, multiplier in patterns:
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                value = int(
                    match.group(1)
                )

                candidates.append(
                    (
                        match.start(),
                        value
                        * multiplier,
                    )
                )

        if not candidates:
            return None

        lower = text.lower()

        duration_keywords = [
            "duration",
            "for ",
            "sustained",
            "workload",
            "test",
        ]

        ranked: list[
            tuple[int, int]
        ] = []

        for position, seconds in candidates:
            start = max(
                0,
                position - 60,
            )

            context = lower[
                start:
                position + 60
            ]

            score = sum(
                keyword in context
                for keyword
                in duration_keywords
            )

            ranked.append(
                (
                    score,
                    seconds,
                )
            )

        ranked.sort(
            reverse=True
        )

        return ranked[0][1]

    @staticmethod
    def _extract_scope(
        *,
        requirement: RequirementRecord,
        text: str,
    ) -> str | None:

        title = (
            requirement.title.strip()
        )

        if title:
            return title

        cleaned = " ".join(
            text.split()
        )

        if not cleaned:
            return None

        return cleaned[:200]

    @staticmethod
    def _functional_preconditions(
        text: str,
    ) -> list[str]:

        lower = text.lower()

        preconditions: list[str] = []

        if "when " in lower:
            match = re.search(
                r"\bwhen\s+(.+?)(?:,|then|$)",
                text,
                flags=re.IGNORECASE,
            )

            if match:
                preconditions.append(
                    match.group(1).strip()
                )

        if "after " in lower:
            match = re.search(
                r"\bafter\s+(.+?)(?:,|then|$)",
                text,
                flags=re.IGNORECASE,
            )

            if match:
                preconditions.append(
                    match.group(1).strip()
                )

        return preconditions

    @staticmethod
    def _functional_inputs(
        text: str,
    ) -> list[str]:

        lower = text.lower()

        values: list[str] = []

        if "invalid" in lower:
            values.append(
                "Invalid input"
            )

        if "valid" in lower:
            values.append(
                "Valid input"
            )

        if "empty" in lower:
            values.append(
                "Empty input"
            )

        if "missing" in lower:
            values.append(
                "Missing input"
            )

        return values

    @staticmethod
    def _normalize_unit(
        unit: str,
    ) -> str:

        lower = (
            unit.lower().strip()
        )

        if lower in {
            "ms",
            "millisecond",
            "milliseconds",
        }:
            return "milliseconds"

        if lower in {
            "s",
            "sec",
            "secs",
            "second",
            "seconds",
        }:
            return "seconds"

        return lower