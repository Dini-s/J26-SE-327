from __future__ import annotations

import re

from agents.quality_agent.schemas import (
    CandidateEvidenceMatch,
    EvidenceAdequacyAssessment,
    ExpectedEvidenceProfile,
    RequirementValidationUnit,
    RVUAdequacySummary,
    ValidationEvidence,
)


class AdequacyEngine:
    """
    Type-aware QA evidence adequacy engine.

    Semantic relevance, technical adequacy
    and execution success are independent.

    Thresholds are transparent research
    heuristics and should later be evaluated
    against expert-labelled gold-standard data.
    """

    RELEVANCE_THRESHOLD = 0.35
    STRONG_RELEVANCE_THRESHOLD = 0.55

    NEGATIVE_TERMS = {
        "reject",
        "rejected",
        "deny",
        "denied",
        "invalid",
        "expired",
        "blocked",
        "locked",
        "missing",
        "error",
        "fail",
        "failure",
        "unauthorized",
    }

    STATE_TERMS = {
        "remain",
        "persist",
        "state",
        "created",
        "updated",
        "deleted",
        "locked",
        "unlocked",
        "associated",
        "unchanged",
    }

    WEAK_ORACLES = {
        "works",
        "works correctly",
        "looks correct",
        "looks good",
        "ok",
        "okay",
        "success",
        "successful",
        "pass",
    }

    def assess(
        self,
        *,
        profile: ExpectedEvidenceProfile,
        rvu: RequirementValidationUnit,
        match: CandidateEvidenceMatch,
        evidence: ValidationEvidence,
    ) -> EvidenceAdequacyAssessment:

        if (
            profile.support_status
            == "UNSUPPORTED"
        ):
            return self._assessment(
                profile=profile,
                rvu=rvu,
                match=match,
                evidence=evidence,
                adequacy_status=(
                    "UNSUPPORTED"
                ),
                adequacy_score=0.0,
                factors={},
                reasons=[
                    "UNSUPPORTED_NFR_TYPE"
                ],
            )

        if (
            profile.support_status
            == "REVIEW_REQUIRED"
        ):
            return self._assessment(
                profile=profile,
                rvu=rvu,
                match=match,
                evidence=evidence,
                adequacy_status=(
                    "NOT_ASSESSED"
                ),
                adequacy_score=0.0,
                factors={},
                reasons=[
                    "HUMAN_REVIEW_REQUIRED"
                ],
            )

        if (
            profile.requirement_type
            == "NON_FUNCTIONAL"
            and (
                profile
                .requirement_subtype
                == "PERFORMANCE"
            )
        ):
            return (
                self
                ._assess_performance(
                    profile=profile,
                    rvu=rvu,
                    match=match,
                    evidence=evidence,
                )
            )

        if (
            profile.requirement_type
            == "NON_FUNCTIONAL"
        ):
            return self._assessment(
                profile=profile,
                rvu=rvu,
                match=match,
                evidence=evidence,
                adequacy_status=(
                    "NOT_ASSESSED"
                ),
                adequacy_score=0.0,
                factors={},
                reasons=[
                    (
                        "SPECIALIZED_NFR_"
                        "EVIDENCE_REQUIRED"
                    )
                ],
            )

        return (
            self
            ._assess_functional(
                profile=profile,
                rvu=rvu,
                match=match,
                evidence=evidence,
            )
        )

    def summarize(
        self,
        *,
        rvu: RequirementValidationUnit,
        profile: ExpectedEvidenceProfile,
        assessments: list[
            EvidenceAdequacyAssessment
        ],
    ) -> RVUAdequacySummary:

        if (
            profile.support_status
            == "UNSUPPORTED"
        ):
            return RVUAdequacySummary(
                rvu_id=rvu.rvu_id,
                requirement_id=(
                    rvu.requirement_id
                ),
                support_status=(
                    profile.support_status
                ),
                evidence_found=False,
                adequacy_status=(
                    "UNSUPPORTED"
                ),
                reason_codes=[
                    "UNSUPPORTED_NFR_TYPE"
                ],
            )

        if (
            profile.support_status
            == "REVIEW_REQUIRED"
        ):
            return RVUAdequacySummary(
                rvu_id=rvu.rvu_id,
                requirement_id=(
                    rvu.requirement_id
                ),
                support_status=(
                    profile.support_status
                ),
                evidence_found=False,
                adequacy_status=(
                    "NOT_ASSESSED"
                ),
                reason_codes=[
                    "HUMAN_REVIEW_REQUIRED"
                ],
            )

        relevant = [
            item
            for item in assessments
            if (
                item.relevance_score
                >= self.RELEVANCE_THRESHOLD
            )
        ]

        if not relevant:
            return RVUAdequacySummary(
                rvu_id=rvu.rvu_id,
                requirement_id=(
                    rvu.requirement_id
                ),
                support_status=(
                    profile.support_status
                ),
                evidence_found=False,
                adequacy_status=(
                    "INADEQUATE"
                ),
                reason_codes=[
                    "NO_RELEVANT_EVIDENCE"
                ],
            )

        ordered = sorted(
            relevant,
            key=lambda item: (
                item.adequacy_score,
                item.relevance_score,
            ),
            reverse=True,
        )

        best = ordered[0]

        adequate = [
            item
            for item in relevant
            if (
                item.adequacy_status
                == "ADEQUATE"
            )
        ]

        partial = [
            item
            for item in relevant
            if (
                item.adequacy_status
                == "PARTIAL"
            )
        ]

        reasons = sorted(
            {
                reason
                for item
                in relevant
                for reason
                in item.reason_codes
            }
        )

        if adequate:
            status = "ADEQUATE"

            contributing = [
                item.evidence_id
                for item
                in adequate
            ]

        elif partial:
            status = "PARTIAL"

            contributing = [
                item.evidence_id
                for item
                in partial
            ]

        else:
            status = "INADEQUATE"
            contributing = []

        return RVUAdequacySummary(
            rvu_id=rvu.rvu_id,
            requirement_id=(
                rvu.requirement_id
            ),
            support_status=(
                profile.support_status
            ),
            evidence_found=True,
            adequacy_status=status,
            best_evidence_id=(
                best.evidence_id
            ),
            best_relevance_score=(
                best.relevance_score
            ),
            best_adequacy_score=(
                best.adequacy_score
            ),
            adequate_evidence_ids=[
                item.evidence_id
                for item
                in adequate
            ],
            partial_evidence_ids=[
                item.evidence_id
                for item
                in partial
            ],
            contributing_evidence_ids=(
                contributing
            ),
            reason_codes=reasons,
        )

    def _assess_functional(
        self,
        *,
        profile: ExpectedEvidenceProfile,
        rvu: RequirementValidationUnit,
        match: CandidateEvidenceMatch,
        evidence: ValidationEvidence,
    ) -> EvidenceAdequacyAssessment:

        relevance = self._bounded(
            match.similarity_score
        )

        # Functional RVUs can only be
        # automatically assessed using
        # functional test evidence.
        #
        # Performance evidence may be
        # semantically similar to a functional
        # requirement, but semantic similarity
        # alone must never make it technically
        # adequate functional evidence.
        if (
            evidence.evidence_type
            not in {
                "AUTOMATED_TEST",
                "MANUAL_TEST",
            }
        ):
            return self._assessment(
                profile=profile,
                rvu=rvu,
                match=match,
                evidence=evidence,
                adequacy_status=(
                    "INADEQUATE"
                ),
                adequacy_score=0.0,
                factors={
                    "relevance":
                        relevance,
                },
                reasons=[
                    "WRONG_EVIDENCE_TYPE"
                ],
            )

        evidence_text = (
            self._evidence_text(
                evidence
            )
        )

        preconditions = (
            self._list_alignment(
                profile.preconditions,
                evidence_text,
            )
        )

        inputs = (
            self._list_alignment(
                profile.inputs,
                evidence_text,
            )
        )

        condition = (
            self._text_alignment(
                rvu.atomic_text,
                evidence_text,
            )
        )

        scenario = (
            self._scenario_alignment(
                rvu,
                evidence_text,
            )
        )

        outcome = (
            self._list_alignment(
                profile.expected_outcomes,
                evidence_text,
            )
        )

        oracle = (
            self._oracle_strength(
                evidence
            )
        )

        score = (
            0.20 * relevance
            + 0.10 * preconditions
            + 0.10 * inputs
            + 0.15 * condition
            + 0.15 * scenario
            + 0.15 * outcome
            + 0.15 * oracle
        )

        reasons: list[str] = []

        if (
            relevance
            < self.RELEVANCE_THRESHOLD
        ):
            reasons.append(
                "LOW_RELEVANCE"
            )

        elif (
            relevance
            < self
            .STRONG_RELEVANCE_THRESHOLD
        ):
            reasons.append(
                "MODERATE_RELEVANCE"
            )

        if preconditions < 0.40:
            reasons.append(
                "PRECONDITION_MISMATCH"
            )

        if inputs < 0.40:
            reasons.append(
                "INPUT_MISMATCH"
            )

        if condition < 0.55:
            reasons.append(
                "CONDITION_MISMATCH"
            )

        if scenario < 0.50:
            reasons.append(
                "SCENARIO_MISMATCH"
            )

        if outcome < 0.55:
            reasons.append(
                "OUTCOME_MISMATCH"
            )

        if oracle < 0.60:
            reasons.append(
                "WEAK_ORACLE"
            )

        if (
            relevance
            >= self
            .STRONG_RELEVANCE_THRESHOLD
            and score >= 0.72
            and condition >= 0.55
            and scenario >= 0.50
            and outcome >= 0.55
            and oracle >= 0.60
        ):
            status = "ADEQUATE"

        elif (
            relevance
            >= self.RELEVANCE_THRESHOLD
            and score >= 0.45
        ):
            status = "PARTIAL"

        else:
            status = "INADEQUATE"

        return self._assessment(
            profile=profile,
            rvu=rvu,
            match=match,
            evidence=evidence,
            adequacy_status=status,
            adequacy_score=score,
            factors={
                "relevance":
                    relevance,

                "precondition_alignment":
                    preconditions,

                "input_alignment":
                    inputs,

                "condition_alignment":
                    condition,

                "scenario_alignment":
                    scenario,

                "outcome_alignment":
                    outcome,

                "oracle_strength":
                    oracle,
            },
            reasons=reasons,
        )

    def _assess_performance(
        self,
        *,
        profile: ExpectedEvidenceProfile,
        rvu: RequirementValidationUnit,
        match: CandidateEvidenceMatch,
        evidence: ValidationEvidence,
    ) -> EvidenceAdequacyAssessment:

        relevance = self._bounded(
            match.similarity_score
        )

        if (
            evidence.evidence_type
            != "PERFORMANCE_EVIDENCE"
        ):
            return self._assessment(
                profile=profile,
                rvu=rvu,
                match=match,
                evidence=evidence,
                adequacy_status=(
                    "INADEQUATE"
                ),
                adequacy_score=0.0,
                factors={
                    "relevance":
                        relevance
                },
                reasons=[
                    "WRONG_EVIDENCE_TYPE"
                ],
            )

        metric = self._equal(
            profile.metric,
            evidence.metric,
        )

        percentile = self._equal(
            profile.percentile,
            evidence.percentile,
        )

        load = self._minimum(
            profile.load,
            evidence.load,
        )

        duration = self._minimum(
            profile.duration_seconds,
            evidence.duration_seconds,
        )

        threshold = (
            self
            ._threshold_alignment(
                profile,
                evidence,
            )
        )

        scope = self._text_alignment(
            profile.scope or "",
            evidence.scope or "",
        )

        if not profile.scope:
            scope = 1.0

        score = (
            0.15 * relevance
            + 0.20 * metric
            + 0.10 * percentile
            + 0.15 * load
            + 0.15 * duration
            + 0.15 * threshold
            + 0.10 * scope
        )

        reasons: list[str] = []

        if (
            relevance
            < self.RELEVANCE_THRESHOLD
        ):
            reasons.append(
                "LOW_RELEVANCE"
            )

        elif (
            relevance
            < self
            .STRONG_RELEVANCE_THRESHOLD
        ):
            reasons.append(
                "MODERATE_RELEVANCE"
            )

        if metric == 0.0:
            reasons.append(
                "NFR_METRIC_MISMATCH"
            )

        if percentile == 0.0:
            reasons.append(
                "NFR_PERCENTILE_MISMATCH"
            )

        if load == 0.0:
            reasons.append(
                "NFR_LOAD_MISMATCH"
            )

        if duration == 0.0:
            reasons.append(
                "NFR_DURATION_MISMATCH"
            )

        if threshold == 0.0:
            reasons.append(
                "NFR_THRESHOLD_MISMATCH"
            )

        if scope < 0.40:
            reasons.append(
                "NFR_SCOPE_MISMATCH"
            )

        # The measured value is intentionally
        # not evaluated by adequacy.
        #
        # Adequacy asks whether the evidence
        # configuration is capable of proving
        # the requirement.
        #
        # Actual measured satisfaction is
        # evaluated by ValidationService.

        if (
            relevance
            >= self
            .STRONG_RELEVANCE_THRESHOLD
            and metric == 1.0
            and percentile == 1.0
            and load == 1.0
            and duration == 1.0
            and threshold == 1.0
            and score >= 0.80
        ):
            status = "ADEQUATE"

        elif (
            relevance
            >= self.RELEVANCE_THRESHOLD
            and score >= 0.50
        ):
            status = "PARTIAL"

        else:
            status = "INADEQUATE"

        return self._assessment(
            profile=profile,
            rvu=rvu,
            match=match,
            evidence=evidence,
            adequacy_status=status,
            adequacy_score=score,
            factors={
                "relevance":
                    relevance,

                "metric_alignment":
                    metric,

                "percentile_alignment":
                    percentile,

                "load_alignment":
                    load,

                "duration_alignment":
                    duration,

                "threshold_alignment":
                    threshold,

                "scope_alignment":
                    scope,
            },
            reasons=reasons,
        )

    def _assessment(
        self,
        *,
        profile: ExpectedEvidenceProfile,
        rvu: RequirementValidationUnit,
        match: CandidateEvidenceMatch,
        evidence: ValidationEvidence,
        adequacy_status: str,
        adequacy_score: float,
        factors: dict[str, float],
        reasons: list[str],
    ) -> EvidenceAdequacyAssessment:

        relevance = self._bounded(
            match.similarity_score
        )

        if (
            relevance
            >= self
            .STRONG_RELEVANCE_THRESHOLD
        ):
            relevance_status = (
                "RELEVANT"
            )

        elif (
            relevance
            >= self.RELEVANCE_THRESHOLD
        ):
            relevance_status = (
                "POSSIBLY_RELEVANT"
            )

        else:
            relevance_status = (
                "IRRELEVANT"
            )

        return EvidenceAdequacyAssessment(
            assessment_id=(
                f"AA::{rvu.rvu_id}::"
                f"{evidence.evidence_id}"
            ),
            profile_id=(
                profile.profile_id
            ),
            rvu_id=rvu.rvu_id,
            requirement_id=(
                rvu.requirement_id
            ),
            evidence_id=(
                evidence.evidence_id
            ),
            requirement_type=(
                profile.requirement_type
            ),
            requirement_subtype=(
                profile
                .requirement_subtype
            ),
            retrieval_method=(
                match.retrieval_method
            ),
            retrieval_rank=(
                match.rank
            ),
            relevance_status=(
                relevance_status
            ),
            relevance_score=round(
                relevance,
                6,
            ),
            adequacy_status=(
                adequacy_status
            ),
            adequacy_score=round(
                self._bounded(
                    adequacy_score
                ),
                6,
            ),
            factor_scores={
                key: round(
                    self._bounded(
                        value
                    ),
                    6,
                )
                for (
                    key,
                    value,
                )
                in factors.items()
            },
            reason_codes=sorted(
                set(reasons)
            ),
            execution_status=(
                evidence
                .execution_status
            ),
            source_path=(
                evidence.source_path
            ),
            source_tool=(
                evidence.source_tool
            ),
            synthetic=(
                evidence.synthetic
            ),
            rule_version=(
                "c3-adequacy-v2"
            ),
        )

    def _scenario_alignment(
        self,
        rvu: RequirementValidationUnit,
        evidence_text: str,
    ) -> float:

        behavior = (
            rvu.behavior_type
            .upper()
        )

        lower = (
            evidence_text.lower()
        )

        if behavior == "NEGATIVE":
            return (
                1.0
                if any(
                    value in lower
                    for value
                    in self.NEGATIVE_TERMS
                )
                else 0.25
            )

        if behavior == "BOUNDARY":
            if not rvu.constraints:
                return 0.50

            matched = sum(
                1
                for constraint
                in rvu.constraints
                if (
                    str(
                        constraint
                    ).lower()
                    in lower
                )
            )

            return self._bounded(
                matched
                / len(
                    rvu.constraints
                )
            )

        if behavior in {
            "STATE",
            "STATE_TRANSITION",
        }:
            return (
                1.0
                if any(
                    value in lower
                    for value
                    in self.STATE_TERMS
                )
                else 0.40
            )

        return 1.0

    def _oracle_strength(
        self,
        evidence: ValidationEvidence,
    ) -> float:

        if (
            evidence.evidence_type
            == "AUTOMATED_TEST"
        ):
            return (
                1.0
                if evidence.assertions
                else 0.30
            )

        expected = (
            evidence.expected_result
            or ""
        ).strip()

        if not expected:
            return 0.0

        if (
            expected.lower()
            in self.WEAK_ORACLES
        ):
            return 0.20

        if len(
            self._tokens(
                expected
            )
        ) >= 4:
            return 0.90

        return 0.60

    def _list_alignment(
        self,
        expected: list[str],
        actual: str,
    ) -> float:

        if not expected:
            return 1.0

        values = [
            self._text_alignment(
                value,
                actual,
            )
            for value
            in expected
        ]

        return (
            sum(values)
            / len(values)
        )

    def _text_alignment(
        self,
        expected: str,
        actual: str,
    ) -> float:

        expected_tokens = (
            self._tokens(
                expected
            )
        )

        actual_tokens = (
            self._tokens(
                actual
            )
        )

        if not expected_tokens:
            return 1.0

        overlap = (
            expected_tokens
            & actual_tokens
        )

        ratio = (
            len(overlap)
            / len(
                expected_tokens
            )
        )

        return self._bounded(
            ratio / 0.45
        )

    def _threshold_alignment(
        self,
        profile: ExpectedEvidenceProfile,
        evidence: ValidationEvidence,
    ) -> float:

        if (
            profile.threshold
            is None
        ):
            return 1.0

        if (
            evidence.threshold
            is None
        ):
            return 0.0

        required = (
            self._normalize_numeric(
                profile.threshold,
                profile.unit,
            )
        )

        actual = (
            self._normalize_numeric(
                evidence.threshold,
                evidence.unit,
            )
        )

        operator = (
            profile.operator
            or ""
        )

        if operator in {
            "<",
            "<=",
        }:
            return (
                1.0
                if actual <= required
                else 0.0
            )

        if operator in {
            ">",
            ">=",
        }:
            return (
                1.0
                if actual >= required
                else 0.0
            )

        if operator in {
            "=",
            "==",
        }:
            return (
                1.0
                if actual == required
                else 0.0
            )

        return 0.50

    @staticmethod
    def _minimum(
        required:
        float | int | None,
        actual:
        float | int | None,
    ) -> float:

        if required is None:
            return 1.0

        if actual is None:
            return 0.0

        return (
            1.0
            if actual >= required
            else 0.0
        )

    @staticmethod
    def _equal(
        expected:
        str | None,
        actual:
        str | None,
    ) -> float:

        if expected is None:
            return 1.0

        if actual is None:
            return 0.0

        return (
            1.0
            if (
                expected.lower()
                == actual.lower()
            )
            else 0.0
        )

    @staticmethod
    def _normalize_numeric(
        value: float,
        unit: str | None,
    ) -> float:

        value = float(value)

        if not unit:
            return value

        lower = unit.lower()

        if (
            lower.startswith(
                "millisecond"
            )
            or lower == "ms"
        ):
            return value

        if (
            lower.startswith(
                "second"
            )
            or lower in {
                "s",
                "sec",
            }
        ):
            return (
                value
                * 1000.0
            )

        if lower.startswith(
            "minute"
        ):
            return (
                value
                * 60_000.0
            )

        if lower.startswith(
            "hour"
        ):
            return (
                value
                * 3_600_000.0
            )

        return value

    @staticmethod
    def _evidence_text(
        evidence:
        ValidationEvidence,
    ) -> str:

        values = [
            evidence.title,
            evidence.description,

            " ".join(
                evidence.preconditions
            ),

            " ".join(
                evidence.inputs
            ),

            " ".join(
                evidence.steps
            ),

            evidence.expected_result
            or "",

            " ".join(
                evidence.assertions
            ),

            evidence.metric or "",
            evidence.percentile or "",
            evidence.scope or "",
        ]

        return " ".join(
            value
            for value
            in values
            if value
        )

    @staticmethod
    def _tokens(
        text: str,
    ) -> set[str]:

        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "be",
            "for",
            "from",
            "is",
            "of",
            "or",
            "shall",
            "should",
            "the",
            "to",
            "when",
            "with",
        }

        return {
            token.lower()
            for token
            in re.findall(
                r"[A-Za-z0-9]+",
                text,
            )
            if (
                token.lower()
                not in stop_words
            )
        }

    @staticmethod
    def _bounded(
        value: float,
    ) -> float:

        return max(
            0.0,
            min(
                1.0,
                float(value),
            ),
        )