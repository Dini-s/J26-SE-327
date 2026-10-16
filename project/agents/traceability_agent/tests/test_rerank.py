"""The cross-encoder reranker: fusion, per-requirement selection and the agent hook (no model is loaded)."""

from agents.traceability_agent.agent import TraceabilityAgent
from agents.traceability_agent.reranker.rerank import CrossEncoderReranker
from agents.traceability_agent.retrieval import Candidate
from shared.schemas.traceability import Artifact


def _req(i: str, text: str = "the system shall add a patient") -> Artifact:
    return Artifact(id=i, type="requirement", text=text)


def _code(i: str, text: str) -> Artifact:
    return Artifact(id=i, type="code", text=text)


def _candidates() -> list[Candidate]:
    r1, r2 = _req("R1"), _req("R2")
    a, b, c = _code("A", "class A { void addPatient() {} }"), _code("B", "class B { void other() {} }"), _code("C", "class C { void third() {} }")
    return [Candidate(r1, a, 3.0), Candidate(r1, b, 2.0), Candidate(r1, c, 1.0), Candidate(r2, a, 3.0), Candidate(r2, b, 2.0), Candidate(r2, c, 1.0)]


def test_weight_zero_keeps_stage1_order_and_keeps_per_source():
    reranker = CrossEncoderReranker(weight=0.0, scorer=lambda pairs: [0.0] * len(pairs))
    chosen = reranker.select(_candidates(), keep=2)
    assert [(c.source.id, c.target.id) for c in chosen] == [("R1", "A"), ("R1", "B"), ("R2", "A"), ("R2", "B")]
    assert chosen[0].similarity == 3.0  # the stage-1 score is left untouched


def test_strong_cross_encoder_signal_can_promote_a_lower_ranked_candidate():
    def scorer(pairs):  # the cross-encoder only likes class C
        return [10.0 if "class C" in doc else 0.0 for _, doc in pairs]

    chosen = CrossEncoderReranker(weight=5.0, scorer=scorer).select(_candidates(), keep=1)
    assert [c.target.id for c in chosen] == ["C", "C"]


def test_empty_input():
    assert CrossEncoderReranker(scorer=lambda pairs: []).select([], keep=3) == []


def test_agent_asks_stage1_for_a_pool_then_keeps_top_k():
    class FakeEmbedder:
        def embed_batch(self, texts):
            return [[float(len(t) % 7), 1.0] for t in texts]

    seen = {}

    class SpyReranker:
        def select(self, candidates, keep):
            seen["pool"], seen["keep"] = len(candidates), keep
            return candidates[:keep]

    sources = [_req("R1")]
    targets = [_code(f"T{i}", f"class T{i} {{ void add{i}Patient() {{}} }}") for i in range(8)]
    agent = TraceabilityAgent(uskg=object(), embedder=FakeEmbedder(), llm=object(), top_k=2, reranker=SpyReranker(), rerank_pool=5)
    out = agent.find_candidates(sources, targets)
    assert seen == {"pool": 5, "keep": 2}
    assert len(out) == 2
