"""Stage 1 with more than one embedding model: TF-IDF + MiniLM + a second model, fused with equal weights."""

import numpy as np
import pytest

from agents.traceability_agent.agent import TraceabilityAgent
from agents.traceability_agent.retrieval import embedding_matrix, hybrid_matrix, tfidf_matrix, zscore_fuse
from shared.embeddings import embedder as embedder_mod
from shared.schemas.traceability import Artifact


class Fake:
    """Deterministic 3-D vectors from the text, so the models disagree in a predictable way."""

    def __init__(self, salt: int) -> None:
        self.salt, self.calls = salt, 0

    def embed_batch(self, texts):
        self.calls += 1
        return [[(len(t) * self.salt) % 7 + 1, (sum(map(ord, t)) * self.salt) % 5 + 1, (t.count("o") + self.salt) % 3 + 1] for t in texts]


SOURCES = [Artifact(id=f"R{i}", type="requirement", text=t) for i, t in enumerate(["the user logs in with a password", "list all pets of an owner"])]
TARGETS = [Artifact(id=f"C{i}", type="code", text=t) for i, t in enumerate(["class Login { check(password); }", "class PetList { owner.getPets(); }", "class Cache { }"])]


def test_hybrid_with_extra_embedders_fuses_every_signal_with_equal_weight():
    a, b = Fake(2), Fake(3)
    chunk = 60
    expected = zscore_fuse([tfidf_matrix(SOURCES, TARGETS, chunk_size=chunk), embedding_matrix(SOURCES, TARGETS, a, chunk_size=chunk),
                            embedding_matrix(SOURCES, TARGETS, b, chunk_size=chunk)])
    got = hybrid_matrix(SOURCES, TARGETS, a, chunk_size=chunk, extra_embedders=[b])
    assert np.allclose(got, expected)
    assert np.allclose(hybrid_matrix(SOURCES, TARGETS, a, chunk_size=chunk), zscore_fuse([tfidf_matrix(SOURCES, TARGETS, chunk_size=chunk), embedding_matrix(SOURCES, TARGETS, a, chunk_size=chunk)]))


def test_agent_uses_extras_only_when_given_and_only_for_hybrid():
    main, extra = Fake(2), Fake(3)
    plain = TraceabilityAgent(uskg=object(), embedder=main, llm=object(), top_k=2)
    plain.find_candidates(SOURCES, TARGETS)
    assert main.calls and extra.calls == 0 and plain.extra_embedders == []     # explicit embedder: nothing extra, as measured before
    boosted = TraceabilityAgent(uskg=object(), embedder=Fake(2), llm=object(), top_k=2, extra_embedders=[extra])
    boosted.find_candidates(SOURCES, TARGETS)
    assert extra.calls > 0
    only_embeddings = TraceabilityAgent(uskg=object(), embedder=Fake(2), llm=object(), top_k=2, retrieval="embeddings", extra_embedders=[Fake(5)])
    only_embeddings.find_candidates(SOURCES, TARGETS)                          # runs without error; extras do not apply here


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(embedder_mod, "LOCAL_MODELS_DIR", tmp_path)
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    monkeypatch.delenv("EXTRA_EMBEDDING_MODEL_NAMES", raising=False)
    return tmp_path


def test_default_extra_model_is_used_when_its_folder_exists(models_dir):
    assert embedder_mod.configured_extra_embedders() == []                      # no folder: two signals only
    (models_dir / "c4-codebert").mkdir()
    extras = embedder_mod.configured_extra_embedders()
    assert [e.model_name for e in extras] == [str(models_dir / "c4-codebert")]


def test_extra_models_can_be_listed_or_switched_off(models_dir, monkeypatch):
    (models_dir / "c4-codebert").mkdir()
    monkeypatch.setenv("EXTRA_EMBEDDING_MODEL_NAMES", "")
    assert embedder_mod.configured_extra_embedders() == []
    monkeypatch.setenv("EXTRA_EMBEDDING_MODEL_NAMES", " c4-codebert , other-model ")
    assert [e.model_name for e in embedder_mod.configured_extra_embedders()] == [str(models_dir / "c4-codebert"), "other-model"]
