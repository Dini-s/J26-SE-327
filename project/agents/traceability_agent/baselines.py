"""Baselines the full pipeline is compared against (no LLM verification step).

* TF-IDF / cosine: classic information-retrieval baseline.
* Embeddings only: the agent's stage 1 on its own, without the LLM stage.
"""

from typing import Any, Sequence

from sklearn.feature_extraction.text import TfidfVectorizer

from agents.traceability_agent.retrieval import Candidate, cosine_matrix, select_candidates
from shared.schemas.traceability import Artifact


def tfidf_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    top_k: int = 10,
    threshold: float = 0.1,
) -> list[Candidate]:
    """TF-IDF cosine-similarity baseline.

    The vocabulary is fitted on all source and target texts together.

    Args:
        sources: Source artifacts.
        targets: Target artifacts.
        top_k: Max targets kept per source.
        threshold: Minimum cosine similarity.

    Returns:
        Predicted pairs as candidates.
    """
    if not sources or not targets:
        return []
    matrix = TfidfVectorizer(lowercase=True, stop_words="english").fit_transform(
        [a.text for a in list(sources) + list(targets)]
    )
    src, tgt = matrix[: len(sources)].toarray(), matrix[len(sources) :].toarray()
    return select_candidates(sources, targets, cosine_matrix(src, tgt), top_k, threshold)


def embedding_candidates(
    sources: Sequence[Artifact],
    targets: Sequence[Artifact],
    embedder: Any,
    top_k: int = 10,
    threshold: float = 0.5,
) -> list[Candidate]:
    """Embeddings-only baseline (sentence-transformers similarity, no LLM).

    Args:
        sources: Source artifacts.
        targets: Target artifacts.
        embedder: Object with ``embed_batch(list[str])``.
        top_k: Max targets kept per source.
        threshold: Minimum cosine similarity.

    Returns:
        Predicted pairs as candidates.
    """
    if not sources or not targets:
        return []
    sims = cosine_matrix(
        embedder.embed_batch([a.text for a in sources]),
        embedder.embed_batch([a.text for a in targets]),
    )
    return select_candidates(sources, targets, sims, top_k, threshold)
