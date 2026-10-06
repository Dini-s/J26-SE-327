"""Decay detection: re-verify existing VERIFIED_TRACE links when their content changes.

Verified links go stale silently when the requirement or code changes. This
monitor polls the graph, spots pairs whose text differs from what was verified
(via the stored hash, so unchanged links cost no LLM calls), re-verifies them,
and on failure flags the link as decayed (the edge is kept, never deleted) and
notifies C3 over Redis.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from agents.traceability_agent.config import PASS_THRESHOLD
from agents.traceability_agent.events import DecayEventPublisher
from agents.traceability_agent.preprocess import llm_text
from agents.traceability_agent.utils import content_hash
from shared.llm.client import LLMClient
from shared.schemas.traceability import Artifact, TraceabilityLink

logger = logging.getLogger(__name__)

TARGET_TYPES = ("code", "test", "design")


@dataclass
class DecayResult:
    """Outcome of re-checking one link."""

    link: TraceabilityLink
    rechecked: bool
    decayed: bool = False
    new_confidence: Optional[float] = None
    reason: str = ""
    published: bool = False


class DecayDetector:
    """Re-verifies verified links and flags the ones that no longer hold."""

    def __init__(
        self,
        uskg: Any,
        llm: LLMClient,
        publisher: Optional[DecayEventPublisher] = None,
        pass_threshold: float = PASS_THRESHOLD,
    ) -> None:
        """Wire up dependencies.

        Args:
            uskg: ``USKGClient`` or ``InMemoryUSKG``.
            llm: Verifier used for re-checking.
            publisher: Where to announce decays; ``None`` disables notifications.
            pass_threshold: Confidence below which a link counts as decayed.
        """
        self.uskg = uskg
        self.llm = llm
        self.publisher = publisher
        self.pass_threshold = pass_threshold

    def check_link(
        self, link: TraceabilityLink, requirement: Artifact, target: Artifact
    ) -> DecayResult:
        """Re-verify one link against the current texts and update the graph.

        If it still passes, the edge is refreshed (new confidence, hash and
        ``lastCheckedAt``). If not, it is marked decayed, a DecayFlag is created
        and an event is published. A malformed LLM reply changes nothing.

        Args:
            link: The existing verified link.
            requirement: Current requirement artifact.
            target: Current code/design artifact.

        Returns:
            What happened.
        """
        try:
            verdict = self.llm.verify_link(
                requirement.model_copy(update={"text": llm_text(requirement)}),
                target.model_copy(update={"text": llm_text(target)}),
            )
            confidence = float(verdict["confidence"])
            passed = bool(verdict["is_linked"]) and confidence >= self.pass_threshold
            reasoning = str(verdict["reasoning"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Re-check of %s -> %s failed: %s", link.source_id, link.target_id, exc)
            return DecayResult(link=link, rechecked=False, reason=f"malformed LLM response: {exc}")

        if passed:
            self.uskg.write_link(
                link.model_copy(
                    update={
                        "confidence": confidence,
                        "justification": reasoning,
                        "status": "verified",
                        "text_hash": content_hash(requirement, target),
                    }
                )
            )
            return DecayResult(link=link, rechecked=True, new_confidence=confidence, reason=reasoning)

        self.uskg.mark_decayed(link, new_confidence=confidence, reason=reasoning)
        published = False
        if self.publisher is not None:
            try:
                self.publisher.publish(link.source_id, link.target_id, link.confidence, confidence)
                published = True
            except Exception:  # keep the decay flag even if Redis is down; surface it in the log
                logger.exception("Failed to publish decay event for %s", link.source_id)
        return DecayResult(
            link=link,
            rechecked=True,
            decayed=True,
            new_confidence=confidence,
            reason=reasoning,
            published=published,
        )

    def run(self, force: bool = False) -> list[DecayResult]:
        """Poll all verified links and re-check those whose content changed.

        Args:
            force: Re-check every verified link, even if its text hash is unchanged.

        Returns:
            One result per link that was re-checked.
        """
        requirements = {a.id: a for a in self.uskg.get_artifacts("requirement")}
        targets = {a.id: a for t in TARGET_TYPES for a in self.uskg.get_artifacts(t)}
        results: list[DecayResult] = []
        for link in self.uskg.get_traces(status="verified"):
            requirement, target = requirements.get(link.source_id), targets.get(link.target_id)
            if requirement is None or target is None:
                logger.warning("Skipping %s -> %s: artifact missing", link.source_id, link.target_id)
                continue
            if not force and link.text_hash == content_hash(requirement, target):
                continue  # unchanged since verification
            results.append(self.check_link(link, requirement, target))
        return results
