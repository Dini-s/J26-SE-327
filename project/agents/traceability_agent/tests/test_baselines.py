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
