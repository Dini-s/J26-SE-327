"""Baseline candidate generators (TF-IDF runs for real; it needs no model or network)."""

from agents.traceability_agent.baselines import embedding_candidates, tfidf_candidates
from shared.schemas.traceability import Artifact


def art(i: str, t: str, text: str) -> Artifact:
    return Artifact(id=i, type=t, text=text)


def test_tfidf_matches_on_shared_vocabulary():
    sources = [art("R1", "requirement", "user login password authentication")]
    targets = [
        art("D1", "design", "authentication of the user password during login"),
        art("D2", "design", "render the monthly sales chart"),
    ]
    cands = tfidf_candidates(sources, targets, top_k=5, threshold=0.1)
    assert [c.target.id for c in cands] == ["D1"]


def test_tfidf_empty_inputs():
    assert tfidf_candidates([], [art("D1", "design", "x")]) == []
    assert tfidf_candidates([art("R1", "requirement", "x")], []) == []


def test_embedding_baseline_uses_embedder_vectors():
    class Fake:
        def embed_batch(self, texts):
            return [[1.0, 0.0] if "a" in t else [0.0, 1.0] for t in texts]

    sources = [art("R1", "requirement", "a")]
    targets = [art("D1", "design", "a"), art("D2", "design", "b")]
    cands = embedding_candidates(sources, targets, Fake(), top_k=5, threshold=0.5)
    assert [c.target.id for c in cands] == ["D1"]


def test_zscore_fuse_prefers_targets_that_both_methods_like():
    import numpy as np

    from agents.traceability_agent.retrieval import zscore_fuse

    a = np.array([[0.9, 0.5, 0.1]])  # method 1 ranks target 0 first
    b = np.array([[0.8, 0.9, 0.0]])  # method 2 ranks target 1 first, target 0 second
    fused = zscore_fuse([a, b])
    assert fused.argmax() == 0  # high in both beats high in one
    assert fused.argmin() == 2


def test_hybrid_candidates_uses_both_signals():
    from agents.traceability_agent.baselines import hybrid_candidates

    class Fake:
        def embed_batch(self, texts):
            return [[1.0, 0.0] if "alpha" in t else [0.0, 1.0] for t in texts]

    sources = [art("R1", "requirement", "alpha feature")]
    targets = [art("D1", "design", "alpha feature module"), art("D2", "design", "beta other thing")]
    cands = hybrid_candidates(sources, targets, Fake(), top_k=1)
    assert [c.target.id for c in cands] == ["D1"]


def test_chunk_words_overlaps_and_covers_whole_text():
    from agents.traceability_agent.retrieval import chunk_words

    text = " ".join(f"w{i}" for i in range(100))
    chunks = chunk_words(text, size=40, overlap=10)
    assert chunks[0].split()[0] == "w0" and chunks[1].split()[0] == "w30"  # step = 40 - 10
    assert "w99" in chunks[-1]
    assert chunk_words("short text", size=40) == ["short text"]
    assert chunk_words("", size=40) == [""]


def test_chunked_score_is_the_best_chunk_not_the_whole_file():
    from agents.traceability_agent.baselines import tfidf_candidates

    filler = " ".join(f"noise{i}" for i in range(200))
    sources = [art("R1", "requirement", "reset password token expiry")]
    targets = [
        art("D1", "code", filler + " reset password token expiry " + filler),  # match buried mid-file
        art("D2", "code", " ".join(f"other{i}" for i in range(400))),
    ]
    # unnormalised whole-file TF-IDF dilutes the match; the best chunk keeps it strong
    whole = tfidf_candidates(sources, targets, top_k=2, threshold=-1.0, chunk_size=None)
    chunked = tfidf_candidates(sources, targets, top_k=2, threshold=-1.0, chunk_size=20)
    score = lambda cs: next(c.similarity for c in cs if c.target.id == "D1")
    assert score(chunked) > score(whole) * 3
