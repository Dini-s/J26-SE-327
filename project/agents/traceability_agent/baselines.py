"""Candidate generators without LLM verification: the baselines, and the hybrid retriever.

* TF-IDF / cosine: classic information-retrieval baseline.
* Embeddings only: the agent's stage 1 with sentence embeddings alone.
* Hybrid: TF-IDF and embeddings fused by summing per-source z-scores.
"""

from typing import Any, Optional, Sequence

from agents.traceability_agent.preprocess import retrieval_text
from agents.traceability_agent.retrieval import (
    Candidate,
    TextFn,
    embedding_matrix,
    hybrid_matrix,
    select_candidates,
    tfidf_matrix,
)
from shared.schemas.traceability import Artifact


def tfidf_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    top_k: int = 10,
    threshold: float = 0.1,
    text_fn: TextFn = retrieval_text,
    chunk_size: Optional[int] = None,
) -> list[Candidate]:
    """TF-IDF cosine-similarity baseline.

    Args:
        sources: Source artifacts.
        targets: Target artifacts.
        top_k: Max targets kept per source.
        threshold: Minimum cosine similarity.
        text_fn: Text extractor (default cleans code; pass ``lambda a: a.text`` for raw).
        chunk_size: Score each target as its best ``chunk_size``-word chunk (None = whole text).

    Returns:
        Predicted pairs as candidates.
    """
    if not sources or not targets:
        return []
    return select_candidates(sources, targets, tfidf_matrix(sources, targets, text_fn, chunk_size), top_k, threshold)


def embedding_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    embedder: Any,
    top_k: int = 10,
    threshold: float = 0.5,
    text_fn: TextFn = retrieval_text,
    chunk_size: Optional[int] = None,
) -> list[Candidate]:
    """Embeddings-only baseline (sentence-transformers similarity, no LLM).

    Args:
        sources: Source artifacts.
        targets: Target artifacts.
        embedder: Object with ``embed_batch(list[str])``.
        top_k: Max targets kept per source.
        threshold: Minimum cosine similarity.
        text_fn: Text extractor (default cleans code).
        chunk_size: Score each target as its best ``chunk_size``-word chunk (None = whole text).

    Returns:
        Predicted pairs as candidates.
    """
    if not sources or not targets:
        return []
    return select_candidates(
        sources, targets, embedding_matrix(sources, targets, embedder, text_fn, chunk_size), top_k, threshold
    )


def hybrid_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    embedder: Any,
    top_k: int = 10,
    threshold: float = float("-inf"),
    text_fn: TextFn = retrieval_text,
    chunk_size: Optional[int] = None,
) -> list[Candidate]:
    """Hybrid retrieval: TF-IDF and embedding scores fused by z-score.

    Args:
        sources: Source artifacts.
        targets: Target artifacts.
        embedder: Object with ``embed_batch(list[str])``.
        top_k: Max targets kept per source.
        threshold: Minimum fused z-score sum; the default of -inf ranks by top-k only.
        text_fn: Text extractor (default cleans code).
        chunk_size: Score each target as its best ``chunk_size``-word chunk (None = whole text).

    Returns:
        Predicted pairs as candidates.
    """
    if not sources or not targets:
        return []
    return select_candidates(
        sources, targets, hybrid_matrix(sources, targets, embedder, text_fn, chunk_size), top_k, threshold
    )
