"""Shared candidate-selection math, used by the agent and by the baselines."""

from typing import NamedTuple, Sequence

import numpy as np

from shared.schemas.traceability import Artifact


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


def select_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    similarities: np.ndarray,
    top_k: int,
    threshold: float,
) -> list[Candidate]:
    """Keep, per source, the ``top_k`` most similar targets scoring >= ``threshold``.

    Args:
        sources: Source artifacts (rows of ``similarities``).
        targets: Target artifacts (columns of ``similarities``).
        similarities: Similarity matrix.
        top_k: Maximum targets kept per source.
        threshold: Minimum similarity to keep.

    Returns:
        Candidates ordered by source, then by descending similarity.
    """
    if top_k <= 0 or not len(sources) or not len(targets):
        return []
    candidates: list[Candidate] = []
    for i, source in enumerate(sources):
        for j in np.argsort(-similarities[i])[:top_k]:
            score = float(similarities[i, j])
            if score >= threshold:
                candidates.append(Candidate(source, targets[j], score))
    return candidates
