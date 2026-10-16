"""Traceability agent: retrieval-then-verify trace link recovery.

Why two stages (retrieval-then-verify)?
    Comparing every requirement with every artifact using an LLM is too slow and
    costly, and pure embedding similarity is noisy: related-sounding text is not
    necessarily a true trace. The two stages trade off recall and precision:

    1. Embedding similarity is cheap and high-RECALL. It shortlists the top-k
       plausible targets per source so true links are unlikely to be missed.
    2. LLM verification (role-prompted as a "software traceability expert", as in
       TraceLLM) is expensive but high-PRECISION. It only sees the shortlist,
       and filters out the false positives that similarity lets through.

    Rule-based or embedding-only methods must pick one point on the
    precision/recall curve; combining the stages gets both at bounded cost.
"""

import logging
import time
from typing import Any, Callable, Optional

from openai import APIError

from agents.traceability_agent.config import (
    CHUNK_WORDS,
    MAX_VERIFY_SECONDS,
    PASS_THRESHOLD,
    SIMILARITY_THRESHOLD,
    TOP_K,
)
from agents.traceability_agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from agents.traceability_agent.preprocess import llm_text, retrieval_text
from agents.traceability_agent.run_log import RunLogger
from agents.traceability_agent.retrieval import (
    Candidate,
    embedding_matrix,
    hybrid_matrix,
    select_candidates,
    tfidf_matrix,
)
from agents.traceability_agent.utils import content_hash
from shared.embeddings.embedder import Embedder
from shared.llm.client import LLMClient
from shared.schemas.traceability import Artifact, TraceabilityLink, TraceabilityResponse
from shared.uskg.client import USKGClient

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_LLM_FAILURES = 3  # abort instead of grinding through candidates while the LLM server is down

__all__ = ["Candidate", "TraceabilityAgent"]


class TraceabilityAgent:
    """Finds, verifies and stores trace links from requirements to code entities."""

    SOURCE_TYPES: tuple[str, ...] = ("requirement",)
    TARGET_TYPES: tuple[str, ...] = ("code", "test", "design")

    def __init__(
        self,
        uskg: Optional[Any] = None,
        embedder: Optional[Embedder] = None,
        llm: Optional[LLMClient] = None,
        pass_threshold: float = PASS_THRESHOLD,
        retrieval: str = "hybrid",
        top_k: int = TOP_K,
        similarity_threshold: Optional[float] = SIMILARITY_THRESHOLD,
        chunk_size: Optional[int] = CHUNK_WORDS,
        run_logger: Optional[RunLogger] = None,
        project: Optional[str] = None,
        reranker: Optional[Any] = None,
        rerank_pool: int = 20,
    ) -> None:
        """Wire up dependencies (injectable so tests can pass mocks).

        Args:
            uskg: Graph client (``USKGClient`` or ``InMemoryUSKG``); a default
                ``USKGClient`` is created from the environment if omitted.
            embedder: Embedding model wrapper; defaults to the configured model.
            llm: LLM wrapper; defaults to one using the traceability-expert prompts.
            pass_threshold: Minimum LLM confidence for a confirmed link to be kept.
            retrieval: Stage-1 method: ``embeddings``, ``tfidf`` or ``hybrid`` (TF-IDF and
                embeddings fused by z-score).
            top_k: Candidates shortlisted per requirement.
            similarity_threshold: Minimum score to shortlist; ``None`` ranks by ``top_k`` only.
            run_logger: If given, shortlist and verdict events are appended to it for the dashboard.
            project: Only read and link artifacts of this project / repository (``None`` = whole graph).
            chunk_size: Score each target as its best chunk of this many words, so long files
                aren't judged on their first few lines only; ``None`` embeds whole texts.
            reranker: Optional ``CrossEncoderReranker``. Stage 1 then shortlists ``rerank_pool`` candidates per
                requirement and the reranker keeps the best ``top_k`` of them for the LLM (off by default).
            rerank_pool: Candidates per requirement that stage 1 hands to the reranker.
        """
        if retrieval not in ("embeddings", "tfidf", "hybrid"):
            raise ValueError(f"Unknown retrieval method: {retrieval!r}")
        self.retrieval = retrieval
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.chunk_size = chunk_size
        self.run_logger = run_logger
        self.project = project
        self.reranker = reranker
        self.rerank_pool = rerank_pool
        self.uskg = uskg if uskg is not None else USKGClient()
        self.embedder = embedder if embedder is not None else Embedder()
        self.llm = (
            llm
            if llm is not None
            else LLMClient(system_prompt=SYSTEM_PROMPT, user_prompt_template=USER_PROMPT_TEMPLATE)
        )
        self.pass_threshold = pass_threshold
        self.verification_latencies: list[float] = []  # seconds per LLM call (NFR: <= 5 s)

    def load_artifacts(self) -> tuple[list[Artifact], list[Artifact]]:
        """Pull source and target artifacts from the USKG.

        Returns:
            ``(source_artifacts, target_artifacts)``.
        """
        scope = {"project": self.project} if self.project else {}
        sources = [a for t in self.SOURCE_TYPES for a in self.uskg.get_artifacts(t, **scope)]
        targets = [a for t in self.TARGET_TYPES for a in self.uskg.get_artifacts(t, **scope)]
        return sources, targets

    def find_candidates(
        self,
        source_artifacts: list[Artifact],
        target_artifacts: list[Artifact],
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> list[Candidate]:
        """Stage 1 (recall): shortlist likely targets per source by cosine similarity.

        The threshold is deliberately permissive; precision is the verifier's job.

        Args:
            source_artifacts: Artifacts to find links from.
            target_artifacts: Artifacts to find links to.
            top_k: Maximum candidates per source (default: the agent's ``top_k``).
            threshold: Minimum score to shortlist (default: the agent's setting; ``None``
                there means no cutoff).

        Returns:
            Candidates ordered by source, then by descending similarity.
        """
        top_k = self.top_k if top_k is None else top_k
        if threshold is None:
            threshold = self.similarity_threshold if self.similarity_threshold is not None else float("-inf")
        if not source_artifacts or not target_artifacts or top_k <= 0:
            return []
        if self.retrieval == "tfidf":
            similarities = tfidf_matrix(source_artifacts, target_artifacts, retrieval_text, self.chunk_size)
        elif self.retrieval == "hybrid":
            similarities = hybrid_matrix(source_artifacts, target_artifacts, self.embedder, retrieval_text, self.chunk_size)
        else:
            similarities = embedding_matrix(source_artifacts, target_artifacts, self.embedder, retrieval_text, self.chunk_size)
        pool = max(top_k, self.rerank_pool) if self.reranker is not None else top_k
        candidates = select_candidates(source_artifacts, target_artifacts, similarities, pool, threshold)
        if self.reranker is not None:
            candidates = self.reranker.select(candidates, keep=top_k)
        if self.run_logger:
            for source in source_artifacts:
                self.run_logger.emit(
                    "shortlist",
                    source_id=source.id,
                    targets=[
                        {"id": c.target.id, "score": round(c.similarity, 4)}
                        for c in candidates
                        if c.source.id == source.id
                    ],
                )
        return candidates

    def verify_candidates(
        self,
        candidates: list[Candidate],
        on_link: Optional[Callable[[TraceabilityLink], None]] = None,
    ) -> list[TraceabilityLink]:
        """Stage 2 (precision): have the LLM confirm each shortlisted pair.

        A pair is kept only if the LLM says ``is_linked`` with confidence at or
        above ``pass_threshold``. Candidates whose LLM reply is malformed are
        logged and skipped so one bad reply cannot abort the whole run. Transport errors
        (server down, 5xx, timeouts after the SDK's own retries) skip that candidate too,
        but ``MAX_CONSECUTIVE_LLM_FAILURES`` in a row means the server is down and the run
        stops with the error rather than silently verifying nothing.

        Args:
            candidates: Pairs produced by :meth:`find_candidates`.
            on_link: Called with each confirmed link immediately (e.g. to write it to the
                graph), so a crash later in the run does not lose links already confirmed.

        Returns:
            Links for the pairs the LLM confirmed.
        """
        links: list[TraceabilityLink] = []
        consecutive_failures = 0
        if self.run_logger:
            self.run_logger.emit("verify_start", total=len(candidates))
        for index, candidate in enumerate(candidates, start=1):
            try:
                started = time.perf_counter()
                result = self.llm.verify_link(
                    candidate.source.model_copy(update={"text": llm_text(candidate.source)}),
                    candidate.target.model_copy(update={"text": llm_text(candidate.target)}),
                )
                elapsed = time.perf_counter() - started
                self.verification_latencies.append(elapsed)
                if elapsed > MAX_VERIFY_SECONDS:
                    logger.warning("Slow verification (%.1fs > %.1fs)", elapsed, MAX_VERIFY_SECONDS)

                consecutive_failures = 0
                is_linked = result["is_linked"]
                if not isinstance(is_linked, bool):
                    raise ValueError(f"is_linked must be a bool, got {is_linked!r}")
                confidence = float(result["confidence"])
                kept = is_linked and confidence >= self.pass_threshold
                if self.run_logger:
                    self.run_logger.emit(
                        "verdict",
                        index=index,
                        source_id=candidate.source.id,
                        target_id=candidate.target.id,
                        similarity=round(candidate.similarity, 4),
                        is_linked=is_linked,
                        confidence=confidence,
                        reasoning=str(result.get("reasoning", "")),
                        latency=round(elapsed, 2),
                        kept=kept,
                    )
                if not kept:
                    continue
                link = TraceabilityLink(
                    source_id=candidate.source.id,
                    target_id=candidate.target.id,
                    link_type=f"{candidate.source.type}_to_{candidate.target.type}",
                    confidence=confidence,
                    justification=str(result["reasoning"]),
                    text_hash=content_hash(candidate.source, candidate.target),
                )
                links.append(link)
                if on_link is not None:
                    on_link(link)
            except APIError as exc:
                consecutive_failures += 1
                if self.run_logger:
                    self.run_logger.emit(
                        "llm_error",
                        index=index,
                        source_id=candidate.source.id,
                        target_id=candidate.target.id,
                        error=f"{type(exc).__name__}: {str(exc)[:150]}",
                    )
                logger.warning("LLM call failed for %s -> %s: %s", candidate.source.id, candidate.target.id, type(exc).__name__)
                if consecutive_failures >= MAX_CONSECUTIVE_LLM_FAILURES:
                    raise
            except (KeyError, TypeError, ValueError) as exc:
                if self.run_logger:
                    self.run_logger.emit(
                        "malformed",
                        index=index,
                        source_id=candidate.source.id,
                        target_id=candidate.target.id,
                        error=str(exc),
                    )
                logger.warning(
                    "Skipping %s -> %s: malformed LLM response (%s)",
                    candidate.source.id,
                    candidate.target.id,
                    exc,
                )
        return links

    def run(self, write: bool = True, skip_existing: bool = True) -> TraceabilityResponse:
        """Run the full pipeline: load -> find_candidates -> verify -> write.

        Args:
            write: If False, skip persisting to the USKG (used by evaluation).
            skip_existing: Don't re-verify pairs that already have a ``VERIFIED_TRACE``
                edge; the decay monitor owns re-checking those.

        Returns:
            The newly confirmed links.
        """
        sources, targets = self.load_artifacts()
        candidates = self.find_candidates(sources, targets)
        if skip_existing:
            existing = {(t.source_id, t.target_id) for t in self.uskg.get_traces()}
            candidates = [c for c in candidates if (c.source.id, c.target.id) not in existing]
        links = self.verify_candidates(candidates, on_link=self.uskg.write_link if write else None)
        return TraceabilityResponse(links=links)
