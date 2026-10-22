from __future__ import annotations

import re

from agents.quality_agent.schemas import (
    RevalidationChangeCase,
    RevalidationEvidenceDecision,
    RevalidationReport,
)


class RevalidationService:
    """
    Determine whether existing validation evidence
    remains reusable after a requirement change.

    The service evaluates impact on evidence purpose.
    It does not own requirement-change detection.
    """

    BOUNDARY_TERMS = {
        "boundary",
        "limit",
        "threshold",
        "exactly",
        "edge",
    }

    def analyze(
        self,
        case: RevalidationChangeCase,
    ) -> RevalidationReport:

        decisions = [
            self._classify(
                case,
                evidence_case,
            )
            for evidence_case
            in case.evidence_cases
        ]

        reusable = sum(
            item.classification
            == "REUSABLE"
            for item in decisions
        )

        modification_required = sum(
            item.classification
            == "MODIFICATION_REQUIRED"
            for item in decisions
        )

        outdated = sum(
            item.classification
            == "OUTDATED"
            for item in decisions
        )

        new_evidence_required = sum(
            item.classification
            == "NEW_EVIDENCE_REQUIRED"
            for item in decisions
        )

        summary: list[str] = []

        if reusable:
            summary.append(
                f"{reusable} existing validation "
                f"asset(s) remain reusable."
            )

        if modification_required:
            summary.append(
                f"{modification_required} existing "
                f"validation asset(s) require updates."
            )

        if outdated:
            summary.append(
                f"{outdated} existing validation "
                f"asset(s) are outdated and should "
                f"be replaced."
            )

        if new_evidence_required:
            summary.append(
                f"{new_evidence_required} new "
                f"validation asset(s) are required."
            )

        summary.append(
            "Revalidation scope is limited to "
            "the affected RVUs and connected "
            "validation evidence."
        )

        recommended_actions = [
            self._recommended_action(
                decision
            )
            for decision in decisions
            if (
                decision.classification
                != "REUSABLE"
            )
        ]

        return RevalidationReport(
            change_id=case.change_id,
            source=case.source,
            requirement_id=(
                case.requirement_id
            ),
            requirement_type=(
                case.requirement_type
            ),
            requirement_subtype=(
                case.requirement_subtype
            ),
            affected_rvu_ids=(
                case.affected_rvu_ids
            ),
            change_type=(
                case.change_type
            ),
            previous_text=(
                case.previous_text
            ),
            current_text=(
                case.current_text
            ),
            reusable_count=reusable,
            modification_required_count=(
                modification_required
            ),
            outdated_count=outdated,
            new_evidence_required_count=(
                new_evidence_required
            ),
            decisions=decisions,
            summary=summary,
            recommended_actions=(
                recommended_actions
            ),
        )

    def _classify(
        self,
        case: RevalidationChangeCase,
        evidence_case,
    ) -> RevalidationEvidenceDecision:

        if evidence_case.evidence_id is None:
            return RevalidationEvidenceDecision(
                evidence_id=None,
                evidence_name=(
                    evidence_case
                    .evidence_name
                ),
                previous_validation_purpose=(
                    evidence_case
                    .previous_validation_purpose
                ),
                current_validation_purpose=(
                    evidence_case
                    .current_validation_purpose
                ),
                classification=(
                    "NEW_EVIDENCE_REQUIRED"
                ),
                reason=(
                    "No existing evidence artifact "
                    "covers the updated validation "
                    "purpose."
                ),
                action="CREATE",
            )

        previous_purpose = self._normalize(
            evidence_case
            .previous_validation_purpose
        )

        current_purpose = self._normalize(
            evidence_case
            .current_validation_purpose
        )

        if previous_purpose == current_purpose:
            return RevalidationEvidenceDecision(
                evidence_id=(
                    evidence_case.evidence_id
                ),
                evidence_name=(
                    evidence_case
                    .evidence_name
                ),
                previous_validation_purpose=(
                    evidence_case
                    .previous_validation_purpose
                ),
                current_validation_purpose=(
                    evidence_case
                    .current_validation_purpose
                ),
                classification="REUSABLE",
                reason=(
                    "The validation purpose is "
                    "unchanged by the requirement "
                    "update."
                ),
                action="KEEP",
            )

        previous_constraints = (
            self._extract_constraints(
                case.previous_text
            )
        )

        current_constraints = (
            self._extract_constraints(
                case.current_text
            )
        )

        constraint_changed = (
            previous_constraints
            != current_constraints
        )

        evidence_text = self._normalize(
            " ".join(
                [
                    evidence_case
                    .evidence_name,
                    evidence_case
                    .evidence_text,
                    evidence_case
                    .previous_validation_purpose,
                ]
            )
        )

        is_boundary_evidence = any(
            term in evidence_text
            for term in self.BOUNDARY_TERMS
        )

        references_old_constraint = (
            self._references_constraints(
                evidence_text,
                previous_constraints,
            )
        )

        if (
            constraint_changed
            and is_boundary_evidence
        ):
            classification = (
                "MODIFICATION_REQUIRED"
            )
            action = "UPDATE"
            reason = (
                "The evidence validates a boundary "
                "or threshold that changed in the "
                "updated requirement."
            )

        elif (
            constraint_changed
            and references_old_constraint
        ):
            classification = "OUTDATED"
            action = "REPLACE"
            reason = (
                "The evidence explicitly validates "
                "the previous requirement constraint."
            )

        else:
            classification = (
                "MODIFICATION_REQUIRED"
            )
            action = "UPDATE"
            reason = (
                "The validation purpose changed and "
                "the existing evidence must be "
                "updated before reuse."
            )

        return RevalidationEvidenceDecision(
            evidence_id=(
                evidence_case.evidence_id
            ),
            evidence_name=(
                evidence_case.evidence_name
            ),
            previous_validation_purpose=(
                evidence_case
                .previous_validation_purpose
            ),
            current_validation_purpose=(
                evidence_case
                .current_validation_purpose
            ),
            classification=classification,
            reason=reason,
            action=action,
        )

    @staticmethod
    def _extract_constraints(
        text: str,
    ) -> set[str]:

        normalized = text.lower()

        patterns = [
            (
                r"\b\d+(?:\.\d+)?\s*"
                r"(?:ms|milliseconds?|seconds?|"
                r"minutes?|hours?|mb|gb|kb|"
                r"percent|%)\b"
            ),
            (
                r"\bp\d{2}\b"
            ),
            (
                r"\b\d+(?:\.\d+)?\s+"
                r"concurrent\s+users?\b"
            ),
            (
                r"\b\d+(?:\.\d+)?\s+"
                r"(?:requests?|operations?)"
                r"(?:\s+per\s+second)?\b"
            ),
        ]

        values: set[str] = set()

        for pattern in patterns:
            values.update(
                re.findall(
                    pattern,
                    normalized,
                )
            )

        return {
            value.strip()
            for value in values
        }

    @staticmethod
    def _references_constraints(
        text: str,
        constraints: set[str],
    ) -> bool:

        return any(
            constraint in text
            for constraint in constraints
        )

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:

        return " ".join(
            text.lower().split()
        )

    @staticmethod
    def _recommended_action(
        decision: RevalidationEvidenceDecision,
    ) -> str:

        if (
            decision.classification
            == "MODIFICATION_REQUIRED"
        ):
            return (
                f"Update {decision.evidence_name} "
                f"to validate the current "
                f"requirement conditions."
            )

        if (
            decision.classification
            == "OUTDATED"
        ):
            return (
                f"Replace {decision.evidence_name} "
                f"with evidence aligned to the "
                f"updated requirement."
            )

        if (
            decision.classification
            == "NEW_EVIDENCE_REQUIRED"
        ):
            return (
                f"Create {decision.evidence_name} "
                f"to provide the newly required "
                f"validation proof."
            )

        return (
            f"Keep {decision.evidence_name}."
        )