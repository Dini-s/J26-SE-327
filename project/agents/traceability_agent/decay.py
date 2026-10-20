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

from agents.traceability_agent.config import DECAY_MIN_DROP, PASS_THRESHOLD
from agents.traceability_agent.events import DecayEventPublisher
from agents.traceability_agent.preprocess import llm_text
from agents.traceability_agent.run_log import RunLogger
from agents.traceability_agent.semdiff import fingerprint_pair, pair_changes
from agents.traceability_agent.utils import content_hash
from shared.llm.client import LLMClient
from shared.schemas.traceability import Artifact, TraceabilityLink

logger = logging.getLogger(__name__)

TARGET_TYPES = ("code", "test", "design")
# Below this many non-blank characters (after boilerplate such as package/import lines is removed) there is
# nothing to judge. The LLM must not be asked then: small models answer "linked" anyway and invent the evidence.
MIN_TARGET_CHARS = 10
EMPTY_TARGET_REASON = "The code entity no longer contains any code to check against the requirement."


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
        run_logger: Optional[RunLogger] = None,
    ) -> None:
        """Wire up dependencies.

        Args:
            uskg: ``USKGClient`` or ``InMemoryUSKG``.
            llm: Verifier used for re-checking.
            publisher: Where to announce decays; ``None`` disables notifications.
            pass_threshold: Confidence below which a link counts as decayed.
            run_logger: If given, every re-check and decay event is appended for the dashboard.
        """
        self.uskg = uskg
        self.llm = llm
        self.publisher = publisher
        self.pass_threshold = pass_threshold
        self.run_logger = run_logger

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
        current_hash = content_hash(requirement, target)
        if link.reviewed_hash == current_hash and link.review_label in ("correct", "wrong", "unsure"):
            desired = {"correct": "verified", "wrong": "rejected", "unsure": "pending_review"}[link.review_label]
            if link.status != desired:
                self.uskg.write_link(link.model_copy(update={"status": desired, "text_hash": current_hash,
                    "confidence": link.verified_confidence if desired == "verified" and link.verified_confidence is not None else link.confidence}))
            return DecayResult(link=link, rechecked=False, reason="Human decision retained for this version.")
        target_text = llm_text(target)
        if (link.status == "decayed" and link.verified_text_hash
                and link.verified_confidence is not None
                and content_hash(requirement, target) == link.verified_text_hash):
            verdict = {"is_linked": True, "confidence": link.verified_confidence,
                       "reasoning": "Requirement and code exactly match the last verified version. Link restored."}
        elif len("".join(target_text.split())) < MIN_TARGET_CHARS:
            # nothing left to check: the link cannot hold, and no LLM call is spent on it
            verdict = {"is_linked": False, "confidence": 0.0, "reasoning": EMPTY_TARGET_REASON}
        elif semantic := pair_changes(link.sem_fingerprint, requirement, target, target_text):
            # a number, a negation, a boolean or a comparison changed: an 8B model reading topics often misses
            # this, so it is reported directly with the exact change and no LLM call is spent
            verdict = {
                "is_linked": False,
                "confidence": 0.0,
                "reasoning": "Meaning-bearing text changed since the link was verified: " + "; ".join(semantic) + ". Needs review.",
            }
        else:
            try:
                verdict = self.llm.verify_link(
                    requirement.model_copy(update={"text": llm_text(requirement)}),
                    target.model_copy(update={"text": target_text}),
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Re-check of %s -> %s failed: %s", link.source_id, link.target_id, exc)
                return DecayResult(link=link, rechecked=False, reason=f"malformed LLM response: {exc}")
        try:
            confidence = float(verdict["confidence"])
            # Hysteresis: "linked" but just under the threshold is only a decay if confidence really dropped,
            # so a link verified at 0.55 does not decay at 0.49 because of LLM noise.
            dropped = (link.confidence - confidence) >= DECAY_MIN_DROP
            passed = bool(verdict["is_linked"]) and (confidence >= self.pass_threshold or not dropped)
            reasoning = str(verdict["reasoning"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Re-check of %s -> %s failed: %s", link.source_id, link.target_id, exc)
            return DecayResult(link=link, rechecked=False, reason=f"malformed LLM response: {exc}")

        if passed:
            from shared.schemas.link_policy import approval_status
            status = "verified" if (link.status == "decayed" and link.verified_text_hash == current_hash) else approval_status(confidence)
            self.uskg.write_link(
                link.model_copy(
                    update={
                        "confidence": confidence,
                        "justification": reasoning,
                        "status": status,
                        "text_hash": content_hash(requirement, target),
                        "sem_fingerprint": fingerprint_pair(requirement, target, target_text),
                    }
                )
            )
            self._log_recheck(link, confidence, decayed=False, published=False, reason=reasoning, status=status)
            return DecayResult(link=link, rechecked=True, new_confidence=confidence, reason=reasoning)

        if link.status in ("pending_review", "rejected"):
            self.uskg.write_link(link.model_copy(update={"status": "rejected", "confidence": confidence,
                                                        "text_hash": current_hash, "justification": reasoning}))
            self._log_recheck(link, confidence, decayed=False, published=False, reason=reasoning, status="rejected")
            return DecayResult(link=link, rechecked=True, new_confidence=confidence, reason=reasoning)
        self.uskg.mark_decayed(
            link, new_confidence=confidence, reason=reasoning, text_hash=content_hash(requirement, target)
        )
        published = False
        if self.publisher is not None:
            try:
                self.publisher.publish(link.source_id, link.target_id, link.confidence, confidence)
                published = True
            except Exception:  # keep the decay flag even if Redis is down; surface it in the log
                logger.exception("Failed to publish decay event for %s", link.source_id)
        if self.run_logger:
            # logged whether or not Redis delivered it, with a flag, so the dashboard can show the event
            from agents.traceability_agent.events import DecayEventPublisher

            self.run_logger.emit(
                "decay_event",
                delivered=published,
                event=DecayEventPublisher.build_event(link.source_id, link.target_id, link.confidence, confidence),
            )
        self._log_recheck(link, confidence, decayed=True, published=published, reason=reasoning)
        return DecayResult(
            link=link,
            rechecked=True,
            decayed=True,
            new_confidence=confidence,
            reason=reasoning,
            published=published,
        )

    def _log_recheck(self, link: TraceabilityLink, new_confidence: float, decayed: bool, published: bool, reason: str, status: Optional[str] = None) -> None:
        if self.run_logger:
            self.run_logger.emit(
                "recheck",
                source_id=link.source_id,
                target_id=link.target_id,
                previous_confidence=link.confidence,
                new_confidence=new_confidence,
                decayed=decayed,
                restored=link.status == "decayed" and not decayed and status == "verified",
                approval_status=status or ("decayed" if decayed else "verified"),
                published=published,
                reason=reason,
            )

    def run(
        self,
        force: bool = False,
        project: Optional[str] = None,
        only_targets: Optional[set[str]] = None,
        only_sources: Optional[set[str]] = None,
    ) -> list[DecayResult]:
        """Poll verified and decayed links and re-check those whose content changed.

        Args:
            force: Re-check every verified link, even if its text hash is unchanged.
            project: Only links of this project / repository.
            only_targets: Only links to these code entity ids (what a commit touched); links to
                other files are not even looked at, so a commit costs LLM calls only where needed.
            only_sources: Only links from these requirement ids (requirements that were edited). With both
                filters a link is looked at if it matches either.

        Returns:
            One result per link that was re-checked.
        """
        scope = {"project": project} if project else {}
        requirements = {a.id: a for a in self.uskg.get_artifacts("requirement", **scope)}
        targets = {a.id: a for t in TARGET_TYPES for a in self.uskg.get_artifacts(t, **scope)}
        results: list[DecayResult] = []
        # decayed links are watched too: when their text changes again (a fix, a revert) they are re-checked
        # and, if they hold, become verified again. Their stored hash is that of the text last checked.
        for link in self.uskg.get_traces(**scope):
            if (only_targets is not None or only_sources is not None) and not (
                (only_targets is not None and link.target_id in only_targets)
                or (only_sources is not None and link.source_id in only_sources)
            ):
                continue
            requirement, target = requirements.get(link.source_id), targets.get(link.target_id)
            if requirement is None or target is None:
                logger.warning("Skipping %s -> %s: artifact missing", link.source_id, link.target_id)
                continue
            if not force and link.text_hash == content_hash(requirement, target):
                continue  # unchanged since verification
            results.append(self.check_link(link, requirement, target))
        return results
