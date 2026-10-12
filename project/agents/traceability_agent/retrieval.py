"""Candidate-selection math: similarity matrices, rank fusion and top-k selection.

Shared by the agent and the baselines so both are measured identically.
"""

from typing import Any, Callable, NamedTuple, Optional, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from agents.traceability_agent.preprocess import retrieval_text
from shared.schemas.traceability import Artifact

TextFn = Callable[[Artifact], str]


class Candidate(NamedTuple):
    """A shortlisted (source, target) pair with its similarity score."""

    source: Artifact
    target: Artifact
    similarity: float


def normalise_rows(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    """L2-normalise row vectors (zero vectors stay zero)."""
    matrix = np.asarray(vectors, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


def cosine_matrix(
    source_vectors: Sequence[Sequence[float]], target_vectors: Sequence[Sequence[float]]
) -> np.ndarray:
    """Pairwise cosine similarity, shape ``(len(sources), len(targets))``."""
    # numpy 2.0.x on macOS (Accelerate BLAS) emits spurious divide/overflow warnings from
    # matmul even though results are correct (verified against einsum), so silence them.
    with np.errstate(all="ignore"):
        return normalise_rows(source_vectors) @ normalise_rows(target_vectors).T


def chunk_words(text: str, size: int, overlap: Optional[int] = None) -> list[str]:
    """Split text into overlapping windows of ``size`` words (always at least one chunk).

    Embedding models read only their first 128-256 tokens, so a long source file is
    judged on its imports and first lines. Chunking lets every part of the file be seen.

    Args:
        text: Text to split.
        size: Words per chunk.
        overlap: Words shared between neighbouring chunks (default ``size // 4``).

    Returns:
        The chunks, or ``[text]`` if it fits in one.
    """
    words = text.split()
    if len(words) <= size:
        return [text]
    step = max(1, size - (size // 4 if overlap is None else overlap))
    return [" ".join(words[i : i + size]) for i in range(0, len(words), step) if words[i : i + size]]


def _chunk_targets(
    targets: Sequence[Artifact], text_fn: TextFn, chunk_size: Optional[int]
) -> tuple[list[str], np.ndarray]:
    """Chunk every target; return all chunk texts and each target's first-chunk offset."""
    texts: list[str] = []
    starts: list[int] = []
    for target in targets:
        starts.append(len(texts))
        text = text_fn(target)
        texts.extend(chunk_words(text, chunk_size) if chunk_size else [text])
    return texts, np.asarray(starts)


def _best_chunk(scores: np.ndarray, starts: np.ndarray) -> np.ndarray:
    """Collapse per-chunk scores to per-target scores by taking each target's best chunk."""
    return np.maximum.reduceat(scores, starts, axis=1)


def tfidf_matrix(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    text_fn: TextFn = retrieval_text,
    chunk_size: Optional[int] = None,
) -> np.ndarray:
    """TF-IDF cosine similarities; with ``chunk_size``, a target scores as its best chunk."""
    chunks, starts = _chunk_targets(targets, text_fn, chunk_size)
    texts = [text_fn(a) for a in sources] + chunks
    matrix = TfidfVectorizer(lowercase=True, stop_words="english").fit_transform(texts)
    scores = cosine_matrix(matrix[: len(sources)].toarray(), matrix[len(sources):].toarray())
    return _best_chunk(scores, starts)


def embedding_matrix(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    embedder: Any,
    text_fn: TextFn = retrieval_text,
    chunk_size: Optional[int] = None,
) -> np.ndarray:
    """Sentence-embedding cosine similarities; with ``chunk_size``, a target scores as its best chunk."""
    chunks, starts = _chunk_targets(targets, text_fn, chunk_size)
    scores = cosine_matrix(embedder.embed_batch([text_fn(a) for a in sources]), embedder.embed_batch(chunks))
    return _best_chunk(scores, starts)


def zscore_fuse(matrices: Sequence[np.ndarray]) -> np.ndarray:
    """Fuse similarity matrices by summing per-source z-scores.

    Each source's scores are standardised within every matrix (mean 0, std 1 across
    targets) before adding, so TF-IDF and embedding scores become comparable. On iTrust
    this beat reciprocal-rank fusion and the best single method at top-10 (it is a
    small gain; TF-IDF alone is as good or better at larger top-k).

    Args:
        matrices: Similarity matrices of identical shape.

    Returns:
        Fused scores, same shape; higher is better. Not bounded, so rank by top-k
        rather than thresholding.
    """
    fused = np.zeros(np.asarray(matrices[0]).shape, dtype=float)
    for matrix in matrices:
        m = np.asarray(matrix, dtype=float)
        fused += (m - m.mean(axis=1, keepdims=True)) / (m.std(axis=1, keepdims=True) + 1e-9)
    return fused


def hybrid_matrix(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    embedder: Any,
    text_fn: TextFn = retrieval_text,
    chunk_size: Optional[int] = None,
) -> np.ndarray:
    """TF-IDF + embedding similarities fused by z-score (rank by top-k, not a threshold)."""
    return zscore_fuse(
        [
            tfidf_matrix(sources, targets, text_fn, chunk_size),
            embedding_matrix(sources, targets, embedder, text_fn, chunk_size),
        ]
    )


def select_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    similarities: np.ndarray,
    top_k: int,
    threshold: float,
) -> list[Candidate]:
    """Keep, per source, the ``top_k`` highest-scoring targets with score >= ``threshold``.

    Args:
        sources: Source artifacts (rows of ``similarities``).
        targets: Target artifacts (columns of ``similarities``).
        similarities: Score matrix.
        top_k: Maximum targets kept per source.
        threshold: Minimum score to keep.

    Returns:
        Candidates ordered by source, then by descending score.
    """
    if top_k <= 0 or not len(sources) or not len(targets):
        return []
    candidates: list[Candidate] = []
    for i, source in enumerate(sources):
        for j in np.argsort(-similarities[i], kind="stable")[:top_k]:
            score = float(similarities[i, j])
            if score >= threshold:
                candidates.append(Candidate(source, targets[j], score))
    return candidates
