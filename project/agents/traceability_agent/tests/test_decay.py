"""Decay detection, Redis event and in-memory graph behaviour (all mocked)."""

import json
from unittest.mock import MagicMock

import pytest

from agents.traceability_agent.decay import DecayDetector
from agents.traceability_agent.events import DecayEventPublisher
from agents.traceability_agent.utils import content_hash
from shared.schemas.traceability import Artifact, TraceabilityLink
from shared.uskg.memory import InMemoryUSKG

REQ = Artifact(id="R1", type="requirement", text="Tokens expire after 15 minutes.")
CODE = Artifact(id="C1", type="code", text="TOKEN_TTL_SECONDS = 900")


def link_for(req: Artifact = REQ, code: Artifact = CODE, **kw) -> TraceabilityLink:
    base = dict(
        source_id=req.id, target_id=code.id, link_type="requirement_to_code",
        confidence=0.9, justification="implements expiry", text_hash=content_hash(req, code),
    )
    base.update(kw)
    return TraceabilityLink(**base)


def llm_returning(confidence: float, is_linked: bool = True) -> MagicMock:
    llm = MagicMock()
    llm.verify_link.return_value = {"is_linked": is_linked, "confidence": confidence, "reasoning": "r"}
    return llm


def test_unchanged_links_are_not_rechecked():
    store = InMemoryUSKG([REQ, CODE], [link_for()])
    llm = llm_returning(0.9)
    assert DecayDetector(store, llm).run() == []
    llm.verify_link.assert_not_called()


def test_force_rechecks_unchanged_links():
    store = InMemoryUSKG([REQ, CODE], [link_for()])
    llm = llm_returning(0.9)
    assert len(DecayDetector(store, llm).run(force=True)) == 1
    llm.verify_link.assert_called_once()


def test_changed_code_that_still_passes_refreshes_the_edge():
    changed = CODE.model_copy(update={"text": "TOKEN_TTL_SECONDS = 900  # seconds"})
    store = InMemoryUSKG([REQ, changed], [link_for()])
    (result,) = DecayDetector(store, llm_returning(0.85)).run()
    assert not result.decayed
    stored = store.get_traces()[0]
    assert stored.status == "verified" and stored.confidence == 0.85
    assert stored.text_hash == content_hash(REQ, changed)  # won't be re-checked again


def test_failed_recheck_marks_decayed_keeps_edge_and_publishes():
    changed = CODE.model_copy(update={"text": "TOKEN_TTL_SECONDS = 99999"})
    store = InMemoryUSKG([REQ, changed], [link_for(confidence=0.88)])
    publisher = MagicMock()
    (result,) = DecayDetector(store, llm_returning(0.41), publisher=publisher).run()

    assert result.decayed and result.published
    assert len(store.get_traces()) == 1  # edge preserved, not deleted
    assert store.get_traces()[0].status == "decayed"
    assert store.decay_flags[0]["previous_confidence"] == 0.88
    publisher.publish.assert_called_once_with("R1", "C1", 0.88, 0.41)


def test_not_linked_verdict_decays_even_with_high_confidence():
    changed = CODE.model_copy(update={"text": "something else"})
    store = InMemoryUSKG([REQ, changed], [link_for()])
    (result,) = DecayDetector(store, llm_returning(0.95, is_linked=False)).run()
    assert result.decayed


def test_malformed_llm_reply_changes_nothing():
    changed = CODE.model_copy(update={"text": "public void changed() { }"})
    store = InMemoryUSKG([REQ, changed], [link_for()])
    llm = MagicMock()
    llm.verify_link.return_value = {"nonsense": 1}
    (result,) = DecayDetector(store, llm, publisher=MagicMock()).run()
    assert not result.rechecked and not result.decayed
    assert store.get_traces()[0].status == "verified" and store.decay_flags == []


def test_redis_failure_does_not_lose_the_decay_flag():
    changed = CODE.model_copy(update={"text": "changed"})
    store = InMemoryUSKG([REQ, changed], [link_for()])
    publisher = MagicMock()
    publisher.publish.side_effect = ConnectionError("redis down")
    (result,) = DecayDetector(store, llm_returning(0.1), publisher=publisher).run()
    assert result.decayed and not result.published
    assert store.get_traces()[0].status == "decayed"


def test_missing_artifact_is_skipped():
    store = InMemoryUSKG([REQ], [link_for()])  # code entity gone
    llm = llm_returning(0.9)
    assert DecayDetector(store, llm).run() == []
    llm.verify_link.assert_not_called()


def test_decayed_link_is_not_rechecked_until_its_text_changes_again():
    changed = CODE.model_copy(update={"text": "changed"})
    store = InMemoryUSKG([REQ, changed], [link_for()])
    detector = DecayDetector(store, llm_returning(0.1, is_linked=False))
    assert len(detector.run()) == 1  # decays; the hash of the changed text is stored
    llm = llm_returning(0.9)
    assert DecayDetector(store, llm).run() == []  # same text: no new LLM call
    llm.verify_link.assert_not_called()


def test_decayed_link_recovers_when_the_code_is_fixed():
    broken = CODE.model_copy(update={"text": "changed"})
    store = InMemoryUSKG([REQ, broken], [link_for()])
    DecayDetector(store, llm_returning(0.1, is_linked=False)).run()
    assert store.get_traces()[0].status == "decayed"
    store.artifacts[CODE.id] = CODE  # the change is reverted
    results = DecayDetector(store, llm_returning(0.9)).run()
    assert len(results) == 1 and not results[0].decayed
    assert store.get_traces()[0].status == "verified"


def test_publisher_emits_spec_event_json():
    client = MagicMock()
    event = DecayEventPublisher(client=client).publish("REQ-091", "pricing/discount.py", 0.88, 0.41)
    channel, payload = client.publish.call_args[0]
    assert channel == "trace_decayed"
    body = json.loads(payload)
    assert body == event
    assert set(body) == {
        "event", "requirementId", "codeEntityId", "previousConfidence", "newConfidence", "timestamp",
    }
    assert body["event"] == "trace_decayed"
    assert body["timestamp"].endswith("Z")


def test_in_memory_write_link_is_idempotent_and_keeps_verified_at():
    store = InMemoryUSKG([REQ, CODE])
    store.write_link(link_for())
    first = store.get_traces()[0].verified_at
    store.write_link(link_for(confidence=0.7))
    assert len(store.get_traces()) == 1
    assert store.get_traces()[0].verified_at == first
    assert store.get_traces()[0].confidence == pytest.approx(0.7)


def test_emptied_code_decays_without_asking_the_llm():
    """A commit that leaves only a package line must not be judged by the LLM (it invented evidence before)."""
    from unittest.mock import MagicMock

    from agents.traceability_agent.decay import EMPTY_TARGET_REASON, DecayDetector
    from shared.schemas.traceability import Artifact, TraceabilityLink
    from shared.uskg.memory import InMemoryUSKG

    req = Artifact(id="R1", type="requirement", text="Login failures record the IP address and timestamp.")
    code = Artifact(id="C1", type="code", text="package edu.ncsu.csc.itrust.action;")
    link = TraceabilityLink(source_id="R1", target_id="C1", link_type="requirement_to_code", confidence=0.8,
                            justification="j", status="verified", text_hash="old")
    store = InMemoryUSKG([req, code], [link])
    llm = MagicMock()
    result = DecayDetector(store, llm).check_link(link, req, code)
    llm.verify_link.assert_not_called()
    assert result.decayed and result.new_confidence == 0.0 and result.reason == EMPTY_TARGET_REASON
    assert store.traces[("R1", "C1")].status == "decayed" and len(store.decay_flags) == 1


def test_real_code_still_goes_to_the_llm():
    from unittest.mock import MagicMock

    from agents.traceability_agent.decay import DecayDetector
    from shared.schemas.traceability import Artifact, TraceabilityLink
    from shared.uskg.memory import InMemoryUSKG

    req = Artifact(id="R1", type="requirement", text="Login failures record the IP address.")
    code = Artifact(id="C1", type="code", text="public void recordLoginFailure(String ip) { log(ip); save(ip, now()); }")
    link = TraceabilityLink(source_id="R1", target_id="C1", link_type="requirement_to_code", confidence=0.8,
                            justification="j", status="verified", text_hash="old")
    store = InMemoryUSKG([req, code], [link])
    llm = MagicMock()
    llm.verify_link.return_value = {"is_linked": True, "confidence": 0.8, "reasoning": "logs the ip"}
    DecayDetector(store, llm).check_link(link, req, code)
    llm.verify_link.assert_called_once()
