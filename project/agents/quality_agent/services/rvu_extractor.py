from __future__ import annotations

import re
from dataclasses import dataclass

from agents.quality_agent.schemas import (
    RequirementRecord,
    RequirementValidationUnit,
    SourceSpan,
)


@dataclass
class AtomicPart:
    text: str
    source_fragment: str
    start: int
    end: int

    confidence: float

    review_reason: str | None = None


class RVUExtractor:
    SECOND_CLAUSE_VERBS = (
        "remain",
        "become",
        "be",
        "reject",
        "accept",
        "allow",
        "display",
        "return",
        "maintain",
        "record",
        "preserve",
        "provide",
        "support",
        "complete",
        "identify",
        "expose",
        "persist",
        "reset",
        "include",
        "deny",
        "run",
        "achieve",
    )

    def extract(
        self,
        requirements: list[RequirementRecord],
    ) -> list[RequirementValidationUnit]:

        output: list[
            RequirementValidationUnit
        ] = []

        for requirement in requirements:
            rvu_counter = 1

            for criterion in (
                requirement.acceptance_criteria
            ):
                parts = self._split_atomic(
                    criterion.text
                )

                for part in parts:
                    review_reason = (
                        part.review_reason
                    )

                    if (
                        review_reason is None
                        and self
                        ._contains_unresolved_compound(
                            part.text
                        )
                    ):
                        review_reason = (
                            "Potential compound behavior "
                            "remains; human atomicity "
                            "review is recommended."
                        )

                    requires_review = (
                        part.confidence < 0.85
                        or review_reason
                        is not None
                    )

                    output.append(
                        RequirementValidationUnit(
                            rvu_id=(
                                f"{requirement.requirement_id}"
                                f"-RVU-{rvu_counter:02d}"
                            ),
                            requirement_id=(
                                requirement
                                .requirement_id
                            ),
                            ac_id=(
                                criterion.ac_id
                            ),
                            atomic_text=(
                                part.text
                            ),
                            behavior_type=(
                                self
                                ._classify_behavior(
                                    part.text,
                                    requirement.type,
                                    requirement.subtype,
                                )
                            ),
                            source_text=(
                                criterion.text
                            ),
                            source_fragment=(
                                part.source_fragment
                            ),
                            source_span=SourceSpan(
                                start=part.start,
                                end=part.end,
                            ),
                            constraints=(
                                self
                                ._extract_constraints(
                                    part.text
                                )
                            ),
                            confidence=(
                                part.confidence
                            ),
                            requires_review=(
                                requires_review
                            ),
                            review_reason=(
                                review_reason
                            ),
                            version=1,
                            extraction_method=(
                                "DETERMINISTIC_RVU_V2"
                            ),
                        )
                    )

                    rvu_counter += 1

        return (
            self
            ._remove_exact_duplicates(
                output
            )
        )

    def _split_atomic(
        self,
        text: str,
    ) -> list[AtomicPart]:

        clean = " ".join(
            text.strip().split()
        )

        modal = re.search(
            r"\b(shall|must|should)\b",
            clean,
            re.IGNORECASE,
        )

        if not modal:
            return [
                AtomicPart(
                    text=clean,
                    source_fragment=clean,
                    start=0,
                    end=len(clean),
                    confidence=0.80,
                    review_reason=(
                        "No explicit modal verb "
                        "was detected."
                    ),
                )
            ]

        verbs = "|".join(
            self.SECOND_CLAUSE_VERBS
        )

        split_pattern = re.compile(
            rf"\s+and\s+"
            rf"(?=(?:{verbs})\b)",
            re.IGNORECASE,
        )

        conjunction = (
            split_pattern.search(
                clean,
                modal.end(),
            )
        )

        if not conjunction:
            return [
                AtomicPart(
                    text=(
                        self._ensure_period(
                            clean
                        )
                    ),
                    source_fragment=clean,
                    start=0,
                    end=len(clean),
                    confidence=0.96,
                )
            ]

        left_fragment = clean[
            : conjunction.start()
        ].strip()

        right_start = (
            conjunction.end()
        )

        right_fragment = clean[
            right_start:
        ].strip()

        subject = clean[
            : modal.start()
        ].strip()

        modal_word = (
            modal.group(1)
        )

        reconstructed_right = (
            f"{subject} "
            f"{modal_word} "
            f"{right_fragment}"
        ).strip()

        return [
            AtomicPart(
                text=self._ensure_period(
                    left_fragment
                ),
                source_fragment=(
                    left_fragment
                ),
                start=0,
                end=(
                    conjunction.start()
                ),
                confidence=0.92,
            ),
            AtomicPart(
                text=self._ensure_period(
                    reconstructed_right
                ),
                source_fragment=(
                    right_fragment
                ),
                start=right_start,
                end=len(clean),
                confidence=0.88,
            ),
        ]

    @staticmethod
    def _contains_unresolved_compound(
        text: str,
    ) -> bool:
        lower = text.lower()

        if " or " in lower:
            return True

        return bool(
            re.search(
                r"\band\s+"
                r"(?:also\s+)?\w+",
                lower,
            )
        )

    @staticmethod
    def _ensure_period(
        text: str,
    ) -> str:

        if text.endswith(
            (".", "!", "?")
        ):
            return text

        return text + "."

    @staticmethod
    def _classify_behavior(
        text: str,
        requirement_type: str,
        subtype: str,
    ) -> str:

        lower = text.lower()

        if (
            requirement_type.upper()
            == "NON_FUNCTIONAL"
        ):
            return subtype.upper()

        if any(
            token in lower
            for token in (
                "reject",
                "deny",
                "denied",
                "invalid",
                "missing",
                "no match",
                "no-match",
                "not create",
                "not modify",
                "not expose",
            )
        ):
            return "NEGATIVE"

        if any(
            token in lower
            for token in (
                "exactly",
                "greater than",
                "less than",
                "below",
                "at least",
                "after five",
                "after 5",
                "threshold",
                "expire",
                "larger than",
            )
        ):
            return "BOUNDARY"

        if any(
            token in lower
            for token in (
                "remain locked",
                "state",
                "persist",
                "associated",
                "reset",
                "remain unchanged",
            )
        ):
            return "STATE"

        return "POSITIVE"

    @staticmethod
    def _extract_constraints(
        text: str,
    ) -> list[str]:

        number_words = (
            "one|two|three|four|five|"
            "six|seven|eight|nine|ten"
        )

        patterns = [
            r"\bp\d{2}\b",
            r"\b\d+(?:\.\d+)?\s*percent\b",
            r"\b\d+(?:\.\d+)?\s*%\b",
            r"\b\d+(?:\.\d+)?\s*milliseconds?\b",
            r"\b\d+(?:\.\d+)?\s*seconds?\b",
            r"\b\d+(?:\.\d+)?\s*minutes?\b",
            r"\b\d+(?:\.\d+)?\s*hours?\b",
            r"\b\d+\s+concurrent\s+users?\b",
            (
                rf"\b(?:\d+|{number_words})\s+"
                rf"(?:consecutive\s+)?"
                rf"(?:failed\s+)?"
                rf"(?:authentication\s+)?"
                rf"attempts?\b"
            ),
            r"\b\d+(?:\.\d+)?\s*MB\b",
        ]

        matches: list[str] = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                re.IGNORECASE,
            ):
                value = (
                    match.group(0)
                )

                if value not in matches:
                    matches.append(
                        value
                    )

        return matches

    @staticmethod
    def _remove_exact_duplicates(
        rvus: list[
            RequirementValidationUnit
        ],
    ) -> list[
        RequirementValidationUnit
    ]:

        seen: set[
            tuple[str, str]
        ] = set()

        output = []

        for rvu in rvus:
            key = (
                rvu.requirement_id,
                rvu.atomic_text
                .lower()
                .strip(),
            )

            if key in seen:
                continue

            seen.add(key)

            output.append(
                rvu
            )

        return output