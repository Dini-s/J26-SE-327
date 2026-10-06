"""Unit tests for TraceabilityAgent. USKG, LLM and embeddings are all mocked."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from agents.traceability_agent.agent import TraceabilityAgent
from shared.llm.client import LLMResponseError
from shared.schemas.traceability import Artifact, TraceabilityResponse


def art(id_: str, type_: str, text: str) -> Artifact:
    """Build an Artifact for tests."""
    return Artifact(id=id_, type=type_, text=text)


class FakeEmbedder:
    """Maps known texts to fixed 2-D vectors so similarities are predictable."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors[t] for t in texts]


# "login" requirement points along x; targets at various angles to it.
VECTORS = {
    "req login": [1.0, 0.0],
    "code login": [1.0, 0.0],  # cosine 1.0
    "code auth": [0.8, 0.6],  # cosine 0.8
    "code unrelated": [0.0, 1.0],  # cosine 0.0
}


@pytest.fixture
def req() -> Artifact:
    return art("R1", "requirement", "req login")


@pytest.fixture
def targets() -> list[Artifact]:
    return [
        art("C1", "code", "code login"),
        art("C2", "code", "code auth"),
        art("C3", "code", "code unrelated"),
    ]


def make_agent(llm: Any = None, uskg: Any = None) -> TraceabilityAgent:
    """Agent with mocked dependencies; nothing touches the network or a database."""
    if uskg is None:
        uskg = MagicMock()
    uskg.get_traces.return_value = []  # no pre-existing traces unless a test sets them
    return TraceabilityAgent(
        uskg=uskg,
        embedder=FakeEmbedder(VECTORS),  # type: ignore[arg-type]
        llm=llm or MagicMock(),
        retrieval="embeddings",  # the fake embedder only drives this method
        similarity_threshold=0.5,
    )


# ---------- find_candidates ----------


def test_find_candidates_orders_by_similarity_and_applies_threshold(req, targets):
    cands = make_agent().find_candidates([req], targets, top_k=10, threshold=0.5)
    assert [c.target.id for c in cands] == ["C1", "C2"]  # C3 (0.0) below threshold
    assert cands[0].similarity == pytest.approx(1.0)
    assert cands[1].similarity == pytest.approx(0.8)


def test_find_candidates_respects_top_k(req, targets):
    cands = make_agent().find_candidates([req], targets, top_k=1, threshold=0.0)
    assert [c.target.id for c in cands] == ["C1"]


def test_find_candidates_empty_inputs(req, targets):
    agent = make_agent()
    assert agent.find_candidates([], targets) == []
    assert agent.find_candidates([req], []) == []


def test_find_candidates_none_above_threshold(req, targets):
    assert make_agent().find_candidates([req], targets, threshold=1.1) == []


# ---------- verify_candidates ----------


def llm_returning(*results: Any) -> MagicMock:
    llm = MagicMock()
    llm.verify_link.side_effect = list(results)
    return llm


def test_verify_candidates_keeps_only_confirmed(req, targets):
    llm = llm_returning(
        {"is_linked": True, "confidence": 0.9, "reasoning": "implements login"},
        {"is_linked": False, "confidence": 0.2, "reasoning": "different feature"},
    )
    agent = make_agent(llm=llm)
    links = agent.verify_candidates(agent.find_candidates([req], targets))
    assert len(links) == 1
    assert (links[0].source_id, links[0].target_id) == ("R1", "C1")
    assert links[0].link_type == "requirement_to_code"
    assert links[0].confidence == 0.9
    assert links[0].justification == "implements login"


@pytest.mark.parametrize(
    "bad",
    [
        LLMResponseError("not json"),
        {"confidence": 0.9, "reasoning": "missing is_linked"},
        {"is_linked": "yes", "confidence": 0.9, "reasoning": "non-bool"},
        {"is_linked": True, "confidence": 7, "reasoning": "confidence out of range"},
        {"is_linked": True, "confidence": "high", "reasoning": "non-numeric confidence"},
    ],
)
def test_verify_candidates_skips_malformed_response(req, targets, bad):
    good = {"is_linked": True, "confidence": 0.8, "reasoning": "ok"}
    agent = make_agent(llm=llm_returning(bad, good))
    links = agent.verify_candidates(agent.find_candidates([req], targets))
    assert [link.target_id for link in links] == ["C2"]  # first skipped, second kept


# ---------- run ----------


def test_run_end_to_end_writes_and_returns_links(req, targets):
    uskg = MagicMock()
    uskg.get_artifacts.side_effect = lambda t: {
        "requirement": [req],
        "code": targets,
    }.get(t, [])
    llm = llm_returning(
        {"is_linked": True, "confidence": 0.95, "reasoning": "login flow"},
        {"is_linked": False, "confidence": 0.1, "reasoning": "unrelated"},
    )
    response = make_agent(llm=llm, uskg=uskg).run()

    assert isinstance(response, TraceabilityResponse)
    assert [(l.source_id, l.target_id) for l in response.links] == [("R1", "C1")]
    uskg.write_link.assert_called_once_with(response.links[0])


def test_run_with_no_artifacts_does_nothing():
    uskg = MagicMock()
    uskg.get_artifacts.return_value = []
    llm = MagicMock()
    response = make_agent(llm=llm, uskg=uskg).run()
    assert response.links == []
    llm.verify_link.assert_not_called()
    uskg.write_link.assert_not_called()


def test_run_with_no_candidates_above_threshold_skips_llm(req):
    far = art("C3", "code", "code unrelated")  # cosine 0.0 with req
    uskg = MagicMock()
    uskg.get_artifacts.side_effect = lambda t: {"requirement": [req], "code": [far]}.get(t, [])
    llm = MagicMock()
    response = make_agent(llm=llm, uskg=uskg).run()
    assert response.links == []
    llm.verify_link.assert_not_called()
    uskg.write_link.assert_not_called()


def test_run_write_false_does_not_persist(req, targets):
    uskg = MagicMock()
    uskg.get_artifacts.side_effect = lambda t: {"requirement": [req], "code": targets}.get(t, [])
    llm = llm_returning(
        {"is_linked": True, "confidence": 0.9, "reasoning": "x"},
        {"is_linked": True, "confidence": 0.9, "reasoning": "y"},
    )
    response = make_agent(llm=llm, uskg=uskg).run(write=False)
    assert len(response.links) == 2
    uskg.write_link.assert_not_called()


def test_verify_candidates_drops_low_confidence_even_if_linked(req, targets):
    llm = llm_returning(
        {"is_linked": True, "confidence": 0.3, "reasoning": "weak"},  # below pass threshold
        {"is_linked": True, "confidence": 0.7, "reasoning": "ok"},
    )
    agent = make_agent(llm=llm)
    links = agent.verify_candidates(agent.find_candidates([req], targets))
    assert [l.target_id for l in links] == ["C2"]


def test_verified_links_carry_a_text_hash(req, targets):
    llm = llm_returning({"is_linked": True, "confidence": 0.9, "reasoning": "x"})
    agent = make_agent(llm=llm)
    links = agent.verify_candidates(agent.find_candidates([req], targets, top_k=1))
    assert links[0].text_hash and len(links[0].text_hash) == 64


def test_run_skips_pairs_that_already_have_a_trace(req, targets):
    from shared.schemas.traceability import TraceabilityLink

    uskg = MagicMock()
    uskg.get_artifacts.side_effect = lambda t: {"requirement": [req], "code": targets}.get(t, [])
    llm = llm_returning({"is_linked": True, "confidence": 0.9, "reasoning": "x"})
    agent = make_agent(llm=llm, uskg=uskg)
    uskg.get_traces.return_value = [
        TraceabilityLink(source_id="R1", target_id="C1", link_type="t", confidence=0.9, justification="j")
    ]
    response = agent.run()
    assert [l.target_id for l in response.links] == ["C2"]  # C1 already traced, not re-verified
    assert llm.verify_link.call_count == 1


def test_latencies_are_recorded(req, targets):
    llm = llm_returning({"is_linked": False, "confidence": 0.1, "reasoning": "x"})
    agent = make_agent(llm=llm)
    agent.verify_candidates(agent.find_candidates([req], targets, top_k=1))
    assert len(agent.verification_latencies) == 1


def test_run_logger_records_shortlist_and_verdicts(req, targets, tmp_path):
    import json

    from agents.traceability_agent.run_log import RunLogger

    llm = llm_returning(
        {"is_linked": True, "confidence": 0.9, "reasoning": "yes"},
        {"is_linked": False, "confidence": 0.1, "reasoning": "no"},
    )
    agent = make_agent(llm=llm)
    agent.run_logger = RunLogger(tmp_path / "events.jsonl")
    agent.verify_candidates(agent.find_candidates([req], targets))
    events = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["type"] for e in events] == ["shortlist", "verify_start", "verdict", "verdict"]
    assert [t["id"] for t in events[0]["targets"]] == ["C1", "C2"]
    assert events[2]["kept"] is True and events[3]["kept"] is False
